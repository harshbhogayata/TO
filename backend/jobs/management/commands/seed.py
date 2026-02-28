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

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Allow seeding in production')

    def handle(self, *args, **kwargs):
        if not settings.DEBUG and not kwargs.get('force'):
            self.stderr.write(
                'ERROR: Refusing to seed in production (DEBUG is False). '
                'Use --force to override.\n'
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
            {'name': 'Axiom Labs', 'industry': 'AI & Machine Learning', 'hq': 'Seattle, WA'},
            {'name': 'Vanguard Finance', 'industry': 'Financial Technology', 'hq': 'Chicago, IL'},
            {'name': 'ShieldSec', 'industry': 'Cybersecurity', 'hq': 'Austin, TX'},
            {'name': 'Pixel Republic', 'industry': 'Gaming & Entertainment', 'hq': 'Los Angeles, CA'},
            {'name': 'CloudScale', 'industry': 'Cloud Infrastructure', 'hq': 'Remote'},
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
            # ── Software Engineering ──
            {'title': 'Senior Frontend Developer', 'desc': 'Build modern, performant user interfaces with React and TypeScript. Collaborate closely with designers to deliver pixel-perfect experiences.', 'reqs': '4+ years React experience. Strong TypeScript skills. Eye for design.', 'resp': 'Lead front-end architecture. Mentor junior devs. Code review.', 'skills': ['React', 'TypeScript', 'CSS', 'JavaScript', 'HTML']},
            {'title': 'Backend Systems Engineer', 'desc': 'Design and implement scalable microservices. Optimize database queries and ensure 99.9% uptime.', 'reqs': '5+ years backend development. Python or Go.', 'resp': 'API design. Database optimization. Monitoring.', 'skills': ['Python', 'Django', 'PostgreSQL', 'Docker', 'REST API']},
            {'title': 'Full Stack Developer', 'desc': 'Work across the entire stack — from database design to responsive UIs. Ship features end-to-end.', 'reqs': '3+ years full-stack development.', 'resp': 'Feature development. API integration. Testing.', 'skills': ['React', 'Node.js', 'Python', 'SQL', 'MongoDB']},
            {'title': 'Mobile App Developer', 'desc': 'Build and maintain cross-platform mobile applications with a focus on performance and beautiful UI.', 'reqs': '3+ years mobile development. React Native or Flutter.', 'resp': 'Mobile feature development. App store releases. Performance optimization.', 'skills': ['React Native', 'Flutter', 'Swift', 'Kotlin', 'Mobile Development']},
            {'title': 'Junior Web Developer', 'desc': 'Join our engineering team and grow your skills building real-world web applications.', 'reqs': 'Basic knowledge of HTML, CSS, and JavaScript. Eagerness to learn.', 'resp': 'Bug fixes. Small feature implementation. Writing tests.', 'skills': ['HTML', 'CSS', 'JavaScript', 'Git', 'React']},
            {'title': 'Golang Microservices Engineer', 'desc': 'Design high-throughput distributed systems in Go. Own services from design through production monitoring.', 'reqs': '3+ years Go development. Experience with gRPC or message queues.', 'resp': 'Service design. Performance tuning. On-call rotation.', 'skills': ['Go', 'gRPC', 'Kafka', 'Microservices', 'Docker']},
            {'title': 'Ruby on Rails Developer', 'desc': 'Maintain and extend our core platform built on Rails. Ship clean, well-tested code.', 'reqs': '2+ years Ruby on Rails. Strong testing habits.', 'resp': 'Feature development. Database migrations. Code review.', 'skills': ['Ruby', 'Rails', 'PostgreSQL', 'Redis', 'RSpec']},
            {'title': 'Java Platform Engineer', 'desc': 'Build enterprise-grade backend services with Spring Boot. Ensure reliability at scale.', 'reqs': '4+ years Java. Spring ecosystem experience.', 'resp': 'Service development. Performance monitoring. API design.', 'skills': ['Java', 'Spring Boot', 'Maven', 'MySQL', 'REST API']},
            {'title': 'C++ Systems Developer', 'desc': 'Work on performance-critical systems software including real-time processing and embedded applications.', 'reqs': '5+ years C/C++. Experience with low-latency or embedded systems.', 'resp': 'Core library development. Performance profiling. Code review.', 'skills': ['C++', 'C', 'Linux', 'Embedded Systems', 'Multithreading']},
            {'title': 'PHP Laravel Developer', 'desc': 'Build and maintain web applications using the Laravel framework. Deliver clean, scalable code.', 'reqs': '2+ years PHP/Laravel development.', 'resp': 'Feature development. Database design. API integration.', 'skills': ['PHP', 'Laravel', 'MySQL', 'Vue.js', 'REST API']},
            # ── DevOps / Cloud / Infra ──
            {'title': 'DevOps Engineer', 'desc': 'Automate CI/CD pipelines, manage cloud infrastructure, and improve developer productivity.', 'reqs': '3+ years DevOps/SRE. AWS or GCP experience.', 'resp': 'Infrastructure as code. Monitoring. Incident response.', 'skills': ['AWS', 'Docker', 'Kubernetes', 'Terraform', 'CI/CD']},
            {'title': 'Cloud Solutions Architect', 'desc': 'Design cloud-native architectures on AWS/Azure/GCP. Lead migration projects and optimize costs.', 'reqs': '5+ years cloud architecture. Certification preferred.', 'resp': 'Architecture design. Cost optimization. Team enablement.', 'skills': ['AWS', 'Azure', 'GCP', 'Cloud Architecture', 'Networking']},
            {'title': 'Site Reliability Engineer', 'desc': 'Keep our platform running at 99.99% uptime. Build self-healing infrastructure and monitoring.', 'reqs': '3+ years SRE or infrastructure engineering.', 'resp': 'Incident management. Capacity planning. Automation.', 'skills': ['Linux', 'Prometheus', 'Grafana', 'Kubernetes', 'Python']},
            # ── Data & AI/ML ──
            {'title': 'Data Scientist', 'desc': 'Extract insights from large datasets. Build predictive models and communicate findings to stakeholders.', 'reqs': '3+ years data science. Strong Python and SQL.', 'resp': 'Model building. Data pipeline design. Reporting.', 'skills': ['Python', 'TensorFlow', 'SQL', 'Data Science', 'Pandas']},
            {'title': 'Machine Learning Engineer', 'desc': 'Deploy and scale ML models in production. Build feature pipelines and model monitoring.', 'reqs': '3+ years ML engineering. PyTorch or TensorFlow.', 'resp': 'Model deployment. Feature engineering. A/B testing.', 'skills': ['Python', 'PyTorch', 'TensorFlow', 'MLOps', 'AWS']},
            {'title': 'Data Engineer', 'desc': 'Build and maintain robust data pipelines that power analytics and ML across the organization.', 'reqs': '3+ years data engineering. SQL and Python fluency.', 'resp': 'ETL pipeline development. Data warehouse management. Quality monitoring.', 'skills': ['Python', 'SQL', 'Spark', 'Airflow', 'Snowflake']},
            {'title': 'AI Research Scientist', 'desc': 'Push the boundaries of applied AI. Publish research and prototype novel approaches to NLP and computer vision.', 'reqs': 'PhD or equivalent research experience. Published papers.', 'resp': 'Research. Prototyping. Knowledge transfer to engineering.', 'skills': ['Deep Learning', 'NLP', 'Computer Vision', 'PyTorch', 'Research']},
            {'title': 'Business Intelligence Analyst', 'desc': 'Transform raw data into actionable dashboards and reports that drive business decisions.', 'reqs': '2+ years BI/analytics. Strong SQL and visualization skills.', 'resp': 'Dashboard creation. Ad-hoc analysis. Stakeholder reporting.', 'skills': ['SQL', 'Tableau', 'Power BI', 'Excel', 'Data Analysis']},
            # ── Design ──
            {'title': 'UX/UI Designer', 'desc': 'Shape the user experience across web and mobile products. Conduct research, create wireframes, and build design systems.', 'reqs': '3+ years product design. Proficiency in Figma.', 'resp': 'User research. Wireframing. Design system maintenance.', 'skills': ['Figma', 'UI/UX', 'User Research', 'Sketch', 'Prototyping']},
            {'title': 'Visual / Graphic Designer', 'desc': 'Create stunning visuals for marketing, product, and brand materials across digital and print.', 'reqs': '3+ years graphic design. Adobe Creative Suite mastery.', 'resp': 'Brand asset creation. Marketing collateral. Social media graphics.', 'skills': ['Photoshop', 'Illustrator', 'InDesign', 'Graphic Design', 'Branding']},
            {'title': 'Motion Graphics Designer', 'desc': 'Bring our brand to life through animation and motion design for web, social, and video.', 'reqs': '2+ years motion design. After Effects proficiency.', 'resp': 'Animation production. Video editing. Asset library management.', 'skills': ['After Effects', 'Premiere Pro', 'Motion Design', 'Animation', 'Video Editing']},
            {'title': 'Product Design Lead', 'desc': 'Set the design vision for our product suite. Mentor designers and drive design ops.', 'reqs': '6+ years product design. 2+ years leadership.', 'resp': 'Design strategy. Team mentorship. Design system governance.', 'skills': ['Figma', 'Design Systems', 'Leadership', 'UI/UX', 'Prototyping']},
            # ── Product & Management ──
            {'title': 'Product Manager', 'desc': 'Drive product strategy from ideation to launch. Work cross-functionally with engineering, design, and marketing.', 'reqs': '3+ years PM experience in SaaS.', 'resp': 'Roadmap planning. Sprint management. Stakeholder communication.', 'skills': ['Agile', 'Roadmapping', 'Analytics', 'Jira', 'Product Strategy']},
            {'title': 'Scrum Master', 'desc': 'Facilitate agile ceremonies and remove blockers for engineering teams. Drive continuous improvement.', 'reqs': '2+ years Scrum Master experience. CSM certification preferred.', 'resp': 'Sprint facilitation. Retrospectives. Process improvement.', 'skills': ['Agile', 'Scrum', 'Jira', 'Kanban', 'Coaching']},
            {'title': 'Technical Program Manager', 'desc': 'Coordinate complex cross-team engineering programs. Manage timelines, dependencies, and risk.', 'reqs': '4+ years TPM or similar. Technical background.', 'resp': 'Program planning. Cross-team coordination. Executive reporting.', 'skills': ['Program Management', 'Agile', 'Technical Writing', 'Risk Management', 'Leadership']},
            # ── Marketing & Growth ──
            {'title': 'Digital Marketing Manager', 'desc': 'Own the growth marketing strategy. Plan campaigns, optimize funnels, and analyze performance metrics.', 'reqs': '4+ years digital marketing. B2B SaaS preferred.', 'resp': 'Campaign strategy. SEO/SEM. Analytics reporting.', 'skills': ['SEO', 'Marketing', 'Google Analytics', 'Copywriting', 'Social Media']},
            {'title': 'Content Strategist', 'desc': 'Plan and execute a content strategy that drives organic growth and thought leadership.', 'reqs': '3+ years content marketing. Strong writing skills.', 'resp': 'Editorial calendar. Blog production. SEO optimization.', 'skills': ['Content Strategy', 'SEO', 'Copywriting', 'WordPress', 'Analytics']},
            {'title': 'Social Media Manager', 'desc': 'Grow our social presence across LinkedIn, Twitter/X, and emerging platforms. Build community.', 'reqs': '2+ years social media management. Strong creative instincts.', 'resp': 'Content creation. Community management. Performance analytics.', 'skills': ['Social Media', 'Content Creation', 'Copywriting', 'Analytics', 'Canva']},
            {'title': 'Brand Strategist', 'desc': 'Develop and execute brand strategies that resonate with target audiences across digital channels.', 'reqs': '3+ years brand/marketing strategy.', 'resp': 'Brand positioning. Market research. Content strategy.', 'skills': ['Branding', 'Marketing', 'Copywriting', 'Market Research', 'Strategy']},
            {'title': 'Growth Hacker / Performance Marketer', 'desc': 'Run rapid experiments across paid and organic channels. Optimize CAC and LTV.', 'reqs': '2+ years growth or performance marketing.', 'resp': 'Experiment design. Paid ads management. Funnel optimization.', 'skills': ['Google Ads', 'Facebook Ads', 'A/B Testing', 'Analytics', 'Growth Marketing']},
            # ── Sales & Business ──
            {'title': 'Account Executive (SaaS)', 'desc': 'Close deals with mid-market and enterprise clients. Manage the full sales cycle from discovery to close.', 'reqs': '3+ years B2B SaaS sales. Track record of exceeding quota.', 'resp': 'Pipeline management. Demos. Contract negotiation.', 'skills': ['Sales', 'Salesforce', 'B2B', 'Negotiation', 'CRM']},
            {'title': 'Business Development Representative', 'desc': 'Generate qualified pipeline through outbound prospecting and inbound lead follow-up.', 'reqs': '1+ years SDR/BDR experience or strong communication skills.', 'resp': 'Outbound outreach. Lead qualification. CRM management.', 'skills': ['Sales', 'Cold Outreach', 'Communication', 'CRM', 'LinkedIn']},
            {'title': 'Customer Success Manager', 'desc': 'Ensure client satisfaction, drive adoption, and expand accounts. Be the voice of the customer internally.', 'reqs': '2+ years customer success in SaaS.', 'resp': 'Onboarding. QBRs. Churn prevention. Upselling.', 'skills': ['Customer Success', 'Communication', 'Salesforce', 'Analytics', 'SaaS']},
            # ── HR & People ──
            {'title': 'Technical Recruiter', 'desc': 'Source and hire top engineering talent. Partner with hiring managers to build world-class teams.', 'reqs': '2+ years technical recruiting. ATS experience.', 'resp': 'Sourcing. Screening. Offer management. Employer branding.', 'skills': ['Recruiting', 'Sourcing', 'LinkedIn', 'ATS', 'Communication']},
            {'title': 'People Operations Manager', 'desc': 'Build and scale HR processes, benefits, and culture programs for a growing team.', 'reqs': '3+ years HR/People Ops. HRIS experience.', 'resp': 'HR policy. Benefits administration. Culture programs.', 'skills': ['HR', 'People Operations', 'HRIS', 'Communication', 'Leadership']},
            # ── Finance & Legal ──
            {'title': 'Financial Analyst', 'desc': 'Build financial models, forecast revenue, and provide insights to leadership for strategic decisions.', 'reqs': '2+ years financial analysis. Advanced Excel/Sheets.', 'resp': 'Financial modeling. Budgeting. Variance analysis. Board reporting.', 'skills': ['Financial Modeling', 'Excel', 'SQL', 'Accounting', 'Data Analysis']},
            {'title': 'Legal Counsel (Tech)', 'desc': 'Advise on contracts, IP, privacy compliance, and corporate governance for a fast-growing tech company.', 'reqs': 'JD + 3 years legal experience in tech or startups.', 'resp': 'Contract review. Privacy compliance. IP protection.', 'skills': ['Legal', 'Contract Law', 'Privacy', 'GDPR', 'Compliance']},
            # ── Cybersecurity ──
            {'title': 'Cybersecurity Analyst', 'desc': 'Monitor, detect, and respond to security threats. Conduct vulnerability assessments and security audits.', 'reqs': '2+ years security operations. SIEM experience.', 'resp': 'Threat detection. Incident response. Security audits.', 'skills': ['Cybersecurity', 'SIEM', 'Penetration Testing', 'Networking', 'Linux']},
            {'title': 'Application Security Engineer', 'desc': 'Embed security into the SDLC. Conduct code reviews, threat modeling, and manage bug bounty programs.', 'reqs': '3+ years AppSec. Coding proficiency in at least one language.', 'resp': 'Security reviews. SAST/DAST tooling. Developer training.', 'skills': ['Application Security', 'OWASP', 'Python', 'DevSecOps', 'Threat Modeling']},
            # ── QA & Testing ──
            {'title': 'QA Automation Engineer', 'desc': 'Build and maintain automated test suites for web and API. Improve test coverage and reliability.', 'reqs': '2+ years test automation. Selenium or Playwright.', 'resp': 'Test framework development. CI integration. Bug reporting.', 'skills': ['Selenium', 'Playwright', 'Python', 'CI/CD', 'QA']},
            {'title': 'Manual QA Tester', 'desc': 'Execute test plans, write detailed bug reports, and ensure product quality before every release.', 'reqs': '1+ years QA experience. Strong attention to detail.', 'resp': 'Test case creation. Regression testing. Release verification.', 'skills': ['QA', 'Testing', 'Jira', 'Test Planning', 'Communication']},
            # ── Blockchain / Web3 ──
            {'title': 'Solidity Smart Contract Developer', 'desc': 'Write, audit, and deploy smart contracts on Ethereum and L2 chains. Build DeFi and NFT protocols.', 'reqs': '2+ years Solidity. Understanding of EVM and gas optimization.', 'resp': 'Contract development. Security audits. Protocol design.', 'skills': ['Solidity', 'Ethereum', 'Web3', 'Smart Contracts', 'DeFi']},
            # ── Game Development ──
            {'title': 'Unity Game Developer', 'desc': 'Build immersive gaming experiences with Unity. Work with artists and designers to ship polished games.', 'reqs': '2+ years Unity/C# development. Published title preferred.', 'resp': 'Gameplay programming. Performance optimization. Build pipeline.', 'skills': ['Unity', 'C#', 'Game Development', '3D Modeling', 'Shader Programming']},
            # ── Technical Writing / Support ──
            {'title': 'Technical Writer', 'desc': 'Create clear, concise documentation for APIs, SDKs, and developer tools.', 'reqs': '2+ years technical writing. Developer audience experience.', 'resp': 'API docs. Tutorials. Release notes. Knowledge base.', 'skills': ['Technical Writing', 'API Documentation', 'Markdown', 'Git', 'Communication']},
            {'title': 'Technical Support Engineer', 'desc': 'Troubleshoot complex customer issues, bridge the gap between users and engineering.', 'reqs': '2+ years tech support. Coding/scripting ability.', 'resp': 'Ticket resolution. Root cause analysis. Knowledge base updates.', 'skills': ['Technical Support', 'Troubleshooting', 'SQL', 'Communication', 'Linux']},
            # ── Consulting / Freelance ──
            {'title': 'Freelance WordPress Developer', 'desc': 'Design, build, and maintain custom WordPress sites for our agency clients.', 'reqs': '2+ years WordPress development. Theme and plugin experience.', 'resp': 'Custom theme development. Plugin integration. Site maintenance.', 'skills': ['WordPress', 'PHP', 'CSS', 'JavaScript', 'SEO']},
            {'title': 'IT Consultant', 'desc': 'Advise enterprises on technology strategy, digital transformation, and system architecture.', 'reqs': '5+ years IT consulting. Strong communication.', 'resp': 'Technology assessment. Roadmap creation. Stakeholder management.', 'skills': ['IT Consulting', 'Cloud Architecture', 'Project Management', 'Communication', 'Strategy']},
            # ── Education & Research ──
            {'title': 'Instructional Designer (Tech)', 'desc': 'Create engaging online courses and training materials for technical topics.', 'reqs': '2+ years instructional design. LMS experience.', 'resp': 'Course design. Video scripting. Assessment creation.', 'skills': ['Instructional Design', 'E-Learning', 'Video Production', 'LMS', 'Communication']},
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

            # Add more varied postings
            for i in range(20):
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
