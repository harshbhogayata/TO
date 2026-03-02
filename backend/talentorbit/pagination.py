"""
talentorbit/pagination.py
Standard pagination with a hard max_page_size cap to prevent clients
requesting entire tables in one request (?page_size=999999).
"""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
