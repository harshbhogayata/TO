"""
reviews/views.py
REST API views for company reviews.
"""
import math

from django.db.models import Avg, Count, Q
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsEmailVerified

from .models import CompanyReview, CompanyReviewResponse, ReviewHelpful
from .serializers import (
    CompanyReviewCreateSerializer,
    CompanyReviewListSerializer,
    CompanyReviewResponseCreateSerializer,
    CompanyReviewStatsSerializer,
)


class CompanyReviewListView(generics.ListAPIView):
    """
    GET /api/v1/reviews/<company_id>/
    Public list of approved reviews for a company. Supports filtering.
    """
    serializer_class = CompanyReviewListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        company_id = self.kwargs['company_id']
        qs = CompanyReview.objects.filter(
            company_id=company_id,
            moderation_status='approved',
        ).select_related('author', 'company_response', 'company_response__author')

        # Filters
        department = self.request.query_params.get('department')
        if department and department != 'All':
            qs = qs.filter(department__icontains=department)

        rating = self.request.query_params.get('min_rating')
        if rating:
            try:
                min_r = int(rating)
                qs = qs.annotate(
                    _avg=(
                        (models.F('rating_culture') + models.F('rating_growth') +
                         models.F('rating_compensation') + models.F('rating_management') +
                         models.F('rating_worklife')) / 5.0
                    ),
                ).filter(_avg__gte=min_r)
            except (ValueError, TypeError):
                pass

        role = self.request.query_params.get('role')
        if role and role != 'All':
            qs = qs.filter(role_title__icontains=role)

        sort = self.request.query_params.get('ordering', '-created_at')
        if sort in ('-created_at', '-helpful_count', 'created_at'):
            qs = qs.order_by(sort)

        return qs


class CompanyReviewCreateView(generics.CreateAPIView):
    """
    POST /api/v1/reviews/
    Submit a new company review. Requires authentication + email verification.
    """
    serializer_class = CompanyReviewCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]


class CompanyReviewStatsView(generics.GenericAPIView):
    """
    GET /api/v1/reviews/<company_id>/stats/
    Aggregated review statistics for a company.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, company_id):
        qs = CompanyReview.objects.filter(
            company_id=company_id,
            moderation_status='approved',
        )

        total = qs.count()
        if total == 0:
            return Response({
                'total_reviews': 0,
                'overall_rating': 0,
                'avg_culture': 0, 'avg_growth': 0,
                'avg_compensation': 0, 'avg_management': 0, 'avg_worklife': 0,
                'distribution': {'5': 0, '4': 0, '3': 0, '2': 0, '1': 0},
                'department_breakdown': [],
            })

        avgs = qs.aggregate(
            avg_culture=Avg('rating_culture'),
            avg_growth=Avg('rating_growth'),
            avg_compensation=Avg('rating_compensation'),
            avg_management=Avg('rating_management'),
            avg_worklife=Avg('rating_worklife'),
        )

        overall = sum(v or 0 for v in avgs.values()) / 5.0

        # Star distribution
        distribution = {}
        for star in range(1, 6):
            low = star - 0.5
            high = star + 0.5
            # Count reviews whose overall falls in this star bucket
            count = 0
            for r in qs.only(
                'rating_culture', 'rating_growth', 'rating_compensation',
                'rating_management', 'rating_worklife',
            ):
                avg = r.overall_rating
                if star == 5 and avg >= 4.5:
                    count += 1
                elif star == 1 and avg < 1.5:
                    count += 1
                elif low <= avg < high:
                    count += 1
            distribution[str(star)] = count

        # Department breakdown
        dept_stats = (
            qs.exclude(department='')
            .values('department')
            .annotate(
                count=Count('id'),
                avg_rating=Avg('rating_culture') + Avg('rating_growth') +
                Avg('rating_compensation') + Avg('rating_management') +
                Avg('rating_worklife'),
            )
            .order_by('-count')[:10]
        )
        dept_list = [
            {
                'department': d['department'],
                'count': d['count'],
                'avg_rating': round((d['avg_rating'] or 0) / 5.0, 1),
            }
            for d in dept_stats
        ]

        return Response({
            'total_reviews': total,
            'overall_rating': round(overall, 1),
            'avg_culture': round(avgs['avg_culture'] or 0, 1),
            'avg_growth': round(avgs['avg_growth'] or 0, 1),
            'avg_compensation': round(avgs['avg_compensation'] or 0, 1),
            'avg_management': round(avgs['avg_management'] or 0, 1),
            'avg_worklife': round(avgs['avg_worklife'] or 0, 1),
            'distribution': distribution,
            'department_breakdown': dept_list,
        })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def toggle_helpful(request, review_id):
    """
    POST /api/v1/reviews/<review_id>/helpful/
    Toggle helpful vote. Returns new count.
    """
    try:
        review = CompanyReview.objects.get(
            pk=review_id, moderation_status='approved',
        )
    except CompanyReview.DoesNotExist:
        return Response({'detail': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)

    existing = ReviewHelpful.objects.filter(
        user=request.user, review=review,
    ).first()

    if existing:
        existing.delete()
        review.helpful_count = max(0, review.helpful_count - 1)
        review.save(update_fields=['helpful_count'])
        voted = False
    else:
        ReviewHelpful.objects.create(user=request.user, review=review)
        review.helpful_count += 1
        review.save(update_fields=['helpful_count'])
        voted = True

    return Response({
        'voted': voted,
        'helpful_count': review.helpful_count,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def respond_to_review(request, review_id):
    """
    POST /api/v1/reviews/<review_id>/respond/
    Company official response to a review.
    Only the company that owns the review can respond.
    """
    try:
        review = CompanyReview.objects.select_related('company').get(pk=review_id)
    except CompanyReview.DoesNotExist:
        return Response({'detail': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Check company ownership
    user = request.user
    if not (user.is_staff or (
        hasattr(user, 'company_profile') and
        user.company_profile == review.company
    )):
        return Response(
            {'detail': 'Only the reviewed company can respond.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if hasattr(review, 'company_response'):
        return Response(
            {'detail': 'This review already has a company response.'},
            status=status.HTTP_409_CONFLICT,
        )

    serializer = CompanyReviewResponseCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    response_obj = CompanyReviewResponse.objects.create(
        review=review,
        author=user,
        body=serializer.validated_data['body'],
    )

    return Response(
        CompanyReviewResponseCreateSerializer(response_obj).data
        if False else {'detail': 'Response posted successfully.', 'body': response_obj.body},
        status=status.HTTP_201_CREATED,
    )
