import random
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import CompanyProfile, TalentProfile
from jobs.models import JobPost, Application, SavedJob
from messaging.models import Thread, Message
from notifications.models import Notification
from blog.models import Article
from courses.models import Course

User = get_user_model()


ARTICLES = [
    {
        'category': 'Career Advice',
        'readTime': '5 min read',
        'title': 'Navigating the Modern Technical Interview',
        'excerpt': 'Strategies for demonstrating both coding proficiency and cultural fit over Zoom.',
        'author': 'Alex Thorne',
        'date': 'Oct 18',
        'img': 'https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?q=80&w=600&auto=format&fit=crop',
        'alt': 'Interview setting'
    },
    {
        'category': 'Hiring Trends',
        'readTime': '8 min read',
        'title': 'The Death of the Open Plan Office',
        'excerpt': 'Why top creative talent is demanding specialized remote setups over kombucha on tap.',
        'author': 'M. Sterling',
        'date': 'Oct 12',
        'img': 'https://images.unsplash.com/photo-1522071820081-009f0129c71c?q=80&w=600&auto=format&fit=crop',
        'alt': 'Remote work culture'
    },
    {
        'category': 'Interviews',
        'readTime': '12 min read',
        'title': 'Volume One: Building a Typography-First Digital Agency',
        'excerpt': 'A conversation with the founders on scaling a boutique design studio without losing its soul.',
        'author': 'Sarah Jenkins',
        'date': 'Oct 05',
        'img': 'https://images.unsplash.com/photo-1551434678-e076c223a692?q=80&w=600&auto=format&fit=crop',
        'alt': 'Design system'
    },
    {
        'category': 'Platform Updates',
        'readTime': '3 min read',
        'title': 'Introducing Skill Verification Badges',
        'excerpt': 'TalentOrbit now offers verifiable skill badges backed by quiz performance and portfolio review.',
        'author': 'TalentOrbit Team',
        'date': 'Sep 28',
        'img': 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=600&auto=format&fit=crop',
        'alt': 'Platform update'
    },
    {
        'category': 'Interviews',
        'readTime': '10 min',
        'title': 'Archive: Designing for Density',
        'excerpt': 'Deep dive into complex dashboard UI scaling.',
        'author': 'Guest Author',
        'date': 'Aug 21',
        'img': 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600',
        'alt': 'Dashboard UI'
    },
    {
        'category': 'Career Advice',
        'readTime': '4 min',
        'title': 'Archive: The Freelance Toolkit',
        'excerpt': 'Essential apps for remaining independent and organized.',
        'author': 'Freelance Co.',
        'date': 'May 14',
        'img': 'https://images.unsplash.com/photo-1542361345-89e58247f2d5?w=600',
        'alt': 'Toolkit workspace'
    }
]

COURSES = [
    {
        'category': 'Design',
        'module_name': 'Module 1',
        'title': 'Foundations of Visual Design',
        'duration': '4 weeks',
        'img_url': 'https://images.unsplash.com/photo-1626785774573-4b799315345d?q=80&w=600&auto=format&fit=crop',
        'is_coming_soon': True
    },
    {
        'category': 'Development',
        'module_name': 'Module 2',
        'title': 'Full-Stack Web Development with React & Django',
        'duration': '8 weeks',
        'img_url': 'https://images.unsplash.com/photo-1498050108023-c5249f4df085?q=80&w=600&auto=format&fit=crop',
        'is_coming_soon': True
    },
    {
        'category': 'Marketing',
        'module_name': 'Module 3',
        'title': 'Digital Marketing & Brand Strategy',
        'duration': '6 weeks',
        'img_url': 'https://images.unsplash.com/photo-1533750349088-cd871a92f312?q=80&w=600&auto=format&fit=crop',
        'is_coming_soon': True
    },
    {
        'category': 'Data',
        'module_name': 'Module 4',
        'title': 'Data Science & Analytics Essentials',
        'duration': '6 weeks',
        'img_url': 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=600&auto=format&fit=crop',
        'is_coming_soon': True
    }
]


class Command(BaseCommand):
    help = 'Seeds the database with realistic demo data for all models.'

    def handle(self, *args, **kwargs):
        if not settings.DEBUG:
            self.stderr.write(
                'ERROR: Refusing to seed in production (DEBUG is False). '
                'Set DEBUG=True in .env if you really want to seed.\n'
            )
            return
        self.stdout.write('Seeding database...\n')

        # ──────────────────────────────────────────────
        # 0. Admin user
        # ──────────────────────────────────────────────
        admin_user, created = User.objects.get_or_create(
            email='admin@talentorbit.io',
            defaults={
                'role': 'ADMIN',
                'full_name': 'Platform Admin',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('  ✔ Admin user created (admin@talentorbit.io / admin123)'))
        else:
            self.stdout.write('  • Admin user already exists')

        # ──────────────────────────────────────────────
        # 1. Companies
        # ──────────────────────────────────────────────
        company_data = [
            {'name': 'TechFlow', 'industry': 'Software Engineering', 'hq': 'San Francisco, CA'},
            {'name': 'Volume One', 'industry': 'Design & Branding', 'hq': 'New York, NY'},
            {'name': 'Global Brands', 'industry': 'Marketing & Advertising', 'hq': 'London, UK'},
            {'name': 'Studio Arktos', 'industry': 'Product Design', 'hq': 'Berlin, DE'},
            {'name': 'Nexus Media', 'industry': 'Digital Media', 'hq': 'Toronto, CA'},
        ]

        companies = []
        import uuid
        for cd in company_data:
            email = f"{cd['name'].lower().replace(' ', '')}@example.com"
            user, created = User.objects.get_or_create(email=email, defaults={
                'role': 'COMPANY',
                'full_name': cd['name'] + ' Admin',
                'is_verified': True,
            })
            if created:
                user.set_password('password123')
                user.save()
            # Always ensure profile exists (fixes re-run gaps)
            CompanyProfile.objects.update_or_create(user=user, defaults={
                'legal_name': cd['name'],
                'industry': cd['industry'],
                'registration_number': str(uuid.uuid4())[:12],
                'mission_statement': f"Building the future of {cd['industry'].lower()}.",
                'headquarters': cd['hq'],
                'website': f"https://{cd['name'].lower().replace(' ', '')}.com",
                'is_verified': True,
            })
            companies.append(user)
        self.stdout.write(self.style.SUCCESS(f'  ✔ {len(companies)} company accounts ready'))

        # ──────────────────────────────────────────────
        # 2. Talent users
        # ──────────────────────────────────────────────
        talent_data = [
            {'name': 'Alex Rivera', 'bio': 'Full-stack developer with 5 years of React and Django experience.', 'skills': ['React', 'Django', 'Python', 'TypeScript'], 'location': 'Austin, TX'},
            {'name': 'Jordan Lee', 'bio': 'UX designer passionate about accessibility and user research.', 'skills': ['Figma', 'UI/UX', 'Sketch', 'User Research'], 'location': 'New York, NY'},
            {'name': 'Sam Patel', 'bio': 'Cloud architect specializing in AWS and Kubernetes.', 'skills': ['AWS', 'Docker', 'Kubernetes', 'Go'], 'location': 'Seattle, WA'},
            {'name': 'Morgan Chen', 'bio': 'Data scientist with a focus on NLP and machine learning pipelines.', 'skills': ['Python', 'TensorFlow', 'SQL', 'Data Science'], 'location': 'San Francisco, CA'},
            {'name': 'Taylor Kim', 'bio': 'Marketing strategist with experience in B2B SaaS growth.', 'skills': ['SEO', 'Marketing', 'Analytics', 'Copywriting'], 'location': 'Chicago, IL'},
            {'name': 'Casey Brooks', 'bio': 'Backend engineer who loves building scalable APIs.', 'skills': ['Node.js', 'Python', 'PostgreSQL', 'Redis'], 'location': 'Denver, CO'},
            {'name': 'Riley Zhang', 'bio': 'Creative front-end developer and CSS enthusiast.', 'skills': ['React', 'CSS', 'JavaScript', 'Figma'], 'location': 'Portland, OR'},
            {'name': 'Jamie Santos', 'bio': 'DevOps engineer automating everything.', 'skills': ['Docker', 'AWS', 'CI/CD', 'Terraform'], 'location': 'Remote'},
            {'name': 'Drew Nakamura', 'bio': 'Product manager bridging design and engineering.', 'skills': ['Agile', 'Roadmapping', 'Analytics', 'UI/UX'], 'location': 'Los Angeles, CA'},
            {'name': 'Skyler Thompson', 'bio': 'Junior developer eager to learn and grow.', 'skills': ['JavaScript', 'React', 'HTML', 'CSS'], 'location': 'Miami, FL'},
        ]

        talents = []
        for td in talent_data:
            email = td['name'].lower().replace(' ', '.') + '@example.com'
            user, created = User.objects.get_or_create(email=email, defaults={
                'role': 'TALENT',
                'full_name': td['name'],
                'is_verified': True,
            })
            if created:
                user.set_password('password123')
                user.save()
            # Always ensure profile exists (fixes re-run gaps)
            TalentProfile.objects.update_or_create(user=user, defaults={
                'bio': td['bio'],
                'skills': td['skills'],
                'location': td['location'],
                'is_open_to_work': True,
                'linkedin_url': f"https://linkedin.com/in/{td['name'].lower().replace(' ', '-')}",
            })
            talents.append(user)
        self.stdout.write(self.style.SUCCESS(f'  ✔ {len(talents)} talent accounts ready'))

        # ──────────────────────────────────────────────
        # 3. Job posts
        # ──────────────────────────────────────────────
        job_templates = [
            {'title': 'Senior Frontend Developer', 'desc': 'Build modern, performant user interfaces with React and TypeScript. Collaborate closely with designers to deliver pixel-perfect experiences.', 'reqs': '4+ years React experience. Strong TypeScript skills. Eye for design.', 'resp': 'Lead front-end architecture. Mentor junior devs. Code review.', 'skills': ['React', 'TypeScript', 'CSS', 'Figma']},
            {'title': 'UX/UI Designer', 'desc': 'Shape the user experience across web and mobile products. Conduct research, create wireframes, and build design systems.', 'reqs': '3+ years product design. Proficiency in Figma.', 'resp': 'User research. Wireframing. Design system maintenance.', 'skills': ['Figma', 'UI/UX', 'User Research', 'Sketch']},
            {'title': 'Backend Systems Engineer', 'desc': 'Design and implement scalable microservices. Optimize database queries and ensure 99.9% uptime.', 'reqs': '5+ years backend development. Python or Go.', 'resp': 'API design. Database optimization. Monitoring.', 'skills': ['Python', 'Django', 'PostgreSQL', 'Docker']},
            {'title': 'Product Manager', 'desc': 'Drive product strategy from ideation to launch. Work cross-functionally with engineering, design, and marketing.', 'reqs': '3+ years PM experience in SaaS.', 'resp': 'Roadmap planning. Sprint management. Stakeholder communication.', 'skills': ['Agile', 'Roadmapping', 'Analytics']},
            {'title': 'Creative Director', 'desc': 'Lead the creative vision for campaigns and brand identity. Manage a team of designers and copywriters.', 'reqs': '7+ years in creative/design leadership.', 'resp': 'Brand strategy. Team leadership. Client presentations.', 'skills': ['Figma', 'Marketing', 'Copywriting']},
            {'title': 'DevOps Specialist', 'desc': 'Automate CI/CD pipelines, manage cloud infrastructure, and improve developer productivity.', 'reqs': '3+ years DevOps/SRE. AWS or GCP experience.', 'resp': 'Infrastructure as code. Monitoring. Incident response.', 'skills': ['AWS', 'Docker', 'Kubernetes', 'Terraform']},
            {'title': 'Full Stack Developer', 'desc': 'Work across the entire stack — from database design to responsive UIs. Ship features end-to-end.', 'reqs': '3+ years full-stack development.', 'resp': 'Feature development. API integration. Testing.', 'skills': ['React', 'Node.js', 'Python', 'SQL']},
            {'title': 'Marketing Lead', 'desc': 'Own the growth marketing strategy. Plan campaigns, optimize funnels, and analyze performance metrics.', 'reqs': '4+ years digital marketing. B2B SaaS preferred.', 'resp': 'Campaign strategy. SEO/SEM. Analytics reporting.', 'skills': ['SEO', 'Marketing', 'Analytics', 'Copywriting']},
            {'title': 'Data Scientist', 'desc': 'Extract insights from large datasets. Build predictive models and communicate findings to stakeholders.', 'reqs': '3+ years data science. Strong Python and SQL.', 'resp': 'Model building. Data pipeline design. Reporting.', 'skills': ['Python', 'TensorFlow', 'SQL', 'Data Science']},
            {'title': 'Brand Strategist', 'desc': 'Develop and execute brand strategies that resonate with target audiences across digital channels.', 'reqs': '3+ years brand/marketing strategy.', 'resp': 'Brand positioning. Market research. Content strategy.', 'skills': ['Marketing', 'Copywriting', 'Analytics']},
        ]

        locations = ['New York, NY', 'San Francisco, CA', 'London, UK', 'Remote', 'Berlin, DE', 'Austin, TX', 'Toronto, CA', 'Seattle, WA']

        jobs = []
        if not JobPost.objects.exists():
            for i, tmpl in enumerate(job_templates):
                company = companies[i % len(companies)]
                job = JobPost.objects.create(
                    company=company,
                    title=tmpl['title'],
                    description=tmpl['desc'],
                    requirements=tmpl['reqs'],
                    responsibilities=tmpl['resp'],
                    job_type=random.choice(['full_time', 'part_time', 'contract', 'freelance']),
                    work_mode=random.choice(['remote', 'hybrid', 'on_site']),
                    experience_level=random.choice(['junior', 'mid', 'senior', 'lead']),
                    location=random.choice(locations),
                    salary_min=random.randint(60, 100) * 1000,
                    salary_max=random.randint(110, 180) * 1000,
                    skills_required=tmpl['skills'],
                    status='open',
                )
                jobs.append(job)

            # Add a few more varied postings
            for i in range(10):
                company = random.choice(companies)
                tmpl = random.choice(job_templates)
                job = JobPost.objects.create(
                    company=company,
                    title=tmpl['title'],
                    description=tmpl['desc'],
                    requirements=tmpl['reqs'],
                    responsibilities=tmpl['resp'],
                    job_type=random.choice(['full_time', 'part_time', 'contract', 'freelance']),
                    work_mode=random.choice(['remote', 'hybrid', 'on_site']),
                    experience_level=random.choice(['junior', 'mid', 'senior', 'lead']),
                    location=random.choice(locations),
                    salary_min=random.randint(50, 90) * 1000,
                    salary_max=random.randint(100, 200) * 1000,
                    skills_required=random.sample(tmpl['skills'], k=min(3, len(tmpl['skills']))),
                    status='open',
                )
                jobs.append(job)

            self.stdout.write(self.style.SUCCESS(f'  ✔ {len(jobs)} job posts created'))
        else:
            jobs = list(JobPost.objects.all())
            self.stdout.write('  • Job posts already exist — skipping')

        # ──────────────────────────────────────────────
        # 4. Applications
        # ──────────────────────────────────────────────
        if not Application.objects.exists():
            cover_letters = [
                "I'm excited about this role and believe my skills in {} align perfectly with your requirements.",
                "Having worked on similar projects, I'm confident I can contribute meaningfully to your team.",
                "This position aligns with my career goals and I'd love to bring my experience to {}.",
                "I've been following your company's work and am eager to be part of such an innovative team.",
            ]
            app_count = 0
            statuses = ['pending', 'reviewing', 'shortlisted', 'interviewing', 'offered', 'rejected']
            for talent in talents:
                # Each talent applies to 2-5 random jobs
                sample_jobs = random.sample(jobs, k=min(random.randint(2, 5), len(jobs)))
                for job in sample_jobs:
                    try:
                        Application.objects.create(
                            applicant=talent,
                            job=job,
                            cover_letter=random.choice(cover_letters).format(job.title),
                            status=random.choice(statuses),
                        )
                        app_count += 1
                    except Exception:
                        pass  # skip duplicate (unique_together)
            self.stdout.write(self.style.SUCCESS(f'  ✔ {app_count} applications created'))
        else:
            self.stdout.write('  • Applications already exist — skipping')

        # ──────────────────────────────────────────────
        # 5. Saved jobs
        # ──────────────────────────────────────────────
        if not SavedJob.objects.exists():
            saved_count = 0
            for talent in talents[:6]:
                for job in random.sample(jobs, k=min(3, len(jobs))):
                    try:
                        SavedJob.objects.create(user=talent, job=job)
                        saved_count += 1
                    except Exception:
                        pass
            self.stdout.write(self.style.SUCCESS(f'  ✔ {saved_count} saved jobs created'))
        else:
            self.stdout.write('  • Saved jobs already exist — skipping')

        # ──────────────────────────────────────────────
        # 6. Messaging threads & messages
        # ──────────────────────────────────────────────
        if not Thread.objects.exists():
            thread_count = 0
            msg_count = 0
            conversations = [
                [
                    "Hi! I saw your application for the {} role. Could you tell me more about your experience?",
                    "Thanks for reaching out! I've been working with similar technologies for about 4 years and led a team of 3 on a comparable project.",
                    "That sounds great. Would you be available for a quick call this week?",
                    "Absolutely! I'm free Thursday or Friday afternoon. What works best for you?",
                ],
                [
                    "We'd like to schedule an interview for the {} position. Are you still interested?",
                    "Yes, definitely! I've been looking forward to hearing back. When were you thinking?",
                    "How about next Tuesday at 2pm? We'll do a video call.",
                    "Perfect, I'll be there. Should I prepare anything specific?",
                    "Just be ready to talk about your recent projects and do a short live exercise.",
                ],
                [
                    "Congratulations! We'd like to extend an offer for the {} role.",
                    "That's wonderful news! I'm very excited. Could you send over the details?",
                    "Of course — I'll send the formal offer letter by end of day today.",
                ],
            ]
            # Create threads between talents and companies
            for i, talent in enumerate(talents[:5]):
                company = companies[i % len(companies)]
                job = jobs[i % len(jobs)] if jobs else None
                thread = Thread.objects.create(job=job)
                thread.participants.add(talent, company)
                thread_count += 1

                convo = conversations[i % len(conversations)]
                now = timezone.now()
                for j, body in enumerate(convo):
                    sender = company if j % 2 == 0 else talent
                    Message.objects.create(
                        thread=thread,
                        sender=sender,
                        body=body.format(job.title if job else 'this'),
                        read=(j < len(convo) - 1),  # last message unread
                        sent_at=now - timedelta(hours=len(convo) - j),
                    )
                    msg_count += 1

            self.stdout.write(self.style.SUCCESS(f'  ✔ {thread_count} threads, {msg_count} messages created'))
        else:
            self.stdout.write('  • Messages already exist — skipping')

        # ──────────────────────────────────────────────
        # 7. Notifications
        # ──────────────────────────────────────────────
        if not Notification.objects.exists():
            notif_count = 0
            notif_templates = [
                {'category': 'Application', 'title': 'New application received', 'description': 'A new candidate has applied to your {} posting.'},
                {'category': 'Application', 'title': 'Application status updated', 'description': 'Your application for {} has been moved to the next stage.'},
                {'category': 'Message', 'title': 'New message', 'description': 'You have a new message regarding the {} position.'},
                {'category': 'System', 'title': 'Welcome to TalentOrbit!', 'description': 'Your account has been verified. Start exploring opportunities.'},
                {'category': 'System', 'title': 'Profile tip', 'description': 'Complete your profile to increase your visibility to employers.'},
                {'category': 'Application', 'title': 'Interview scheduled', 'description': 'An interview has been scheduled for your {} application.'},
            ]

            all_users = talents + companies + [admin_user]
            now = timezone.now()
            for user in all_users:
                # 2-4 notifications per user
                for k in range(random.randint(2, 4)):
                    tmpl = random.choice(notif_templates)
                    job_title = jobs[k % len(jobs)].title if jobs else 'a role'
                    Notification.objects.create(
                        user=user,
                        category=tmpl['category'],
                        title=tmpl['title'],
                        description=tmpl['description'].format(job_title),
                        is_read=random.choice([True, False]),
                        created_at=now - timedelta(hours=random.randint(1, 72)),
                    )
                    notif_count += 1
            self.stdout.write(self.style.SUCCESS(f'  ✔ {notif_count} notifications created'))
        else:
            self.stdout.write('  • Notifications already exist — skipping')

        # ──────────────────────────────────────────────
        # 8. Blog articles
        # ──────────────────────────────────────────────
        for item in ARTICLES:
            Article.objects.get_or_create(title=item['title'], defaults=item)
        self.stdout.write(self.style.SUCCESS(f'  ✔ {len(ARTICLES)} blog articles ready'))

        # ──────────────────────────────────────────────
        # 9. Courses
        # ──────────────────────────────────────────────
        for item in COURSES:
            Course.objects.get_or_create(title=item['title'], defaults=item)
        self.stdout.write(self.style.SUCCESS(f'  ✔ {len(COURSES)} courses ready'))

        # ──────────────────────────────────────────────
        # Summary
        # ──────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🎉 Seeding complete!'))
        self.stdout.write('')
        self.stdout.write('  Demo login credentials (all passwords: password123):')
        self.stdout.write('  ─────────────────────────────────────────────────')
        self.stdout.write('  Admin:   admin@talentorbit.io / admin123')
        self.stdout.write('  Company: techflow@example.com  / password123')
        self.stdout.write('  Talent:  alex.rivera@example.com / password123')
        self.stdout.write('')
