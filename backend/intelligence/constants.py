"""
intelligence/constants.py
Skill taxonomy seed data, recommendation weights, threshold configs.
"""

# ─── Recommendation Engine Weights ────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    'content': 0.45,
    'collaborative': 0.30,
    'popularity': 0.15,
    'freshness': 0.10,
}

# ─── Interaction Weights (for collaborative filtering matrix) ─────────────────
INTERACTION_WEIGHTS = {
    'apply': 5.0,
    'save': 3.0,
    'click': 2.0,
    'view': 1.0,
    'unsave': -1.0,
}

# ─── Cache TTLs (seconds) ────────────────────────────────────────────────────
RECOMMENDATION_CACHE_TTL = 900          # 15 minutes
FEATURE_FLAG_CACHE_TTL = 300            # 5 minutes
TFIDF_MODEL_CACHE_TTL = 86400          # 24 hours
INTERACTION_MATRIX_CACHE_TTL = 86400   # 24 hours
ANALYTICS_CACHE_TTL = 600              # 10 minutes
TAXONOMY_CACHE_TTL = 3600              # 1 hour

# ─── Recommendation Limits ────────────────────────────────────────────────────
MAX_RECOMMENDATIONS = 50
DEFAULT_RECOMMENDATIONS = 20
MAX_DIVERSITY_PER_COMPANY = 3
COLD_START_THRESHOLD = 3               # < 3 interactions → content-only
FRESHNESS_DECAY_LAMBDA = 0.05          # Exponential decay rate for job freshness

# ─── Resume Parser ────────────────────────────────────────────────────────────
PARSER_VERSION = 'spacy_v1'
MAX_RESUME_SIZE_MB = 10
SUPPORTED_RESUME_FORMATS = ['pdf', 'docx', 'doc', 'txt']
MIN_SKILL_CONFIDENCE = 0.3
BIO_MAX_LENGTH = 500

# ─── Experience Level Ordinals (for distance scoring) ─────────────────────────
EXPERIENCE_LEVEL_ORDINAL = {
    'entry': 0,
    'junior': 1,
    'mid': 2,
    'senior': 3,
    'lead': 4,
    'executive': 5,
}

# ─── Skill Taxonomy Seed Data (~200 core skills) ─────────────────────────────
# Format: (canonical_name, category, aliases)
INITIAL_SKILLS = [
    # Programming Languages
    ('python', 'Programming', ['Python', 'Python3', 'python3', 'py']),
    ('javascript', 'Programming', ['JavaScript', 'JS', 'js', 'Javascript', 'ECMAScript']),
    ('typescript', 'Programming', ['TypeScript', 'TS', 'ts']),
    ('java', 'Programming', ['Java', 'J2EE']),
    ('csharp', 'Programming', ['C#', 'CSharp', 'C Sharp', '.NET C#']),
    ('cpp', 'Programming', ['C++', 'CPP', 'Cpp']),
    ('c', 'Programming', ['C Language', 'C Programming']),
    ('go', 'Programming', ['Go', 'Golang', 'golang']),
    ('rust', 'Programming', ['Rust', 'Rust Lang']),
    ('ruby', 'Programming', ['Ruby']),
    ('php', 'Programming', ['PHP', 'php']),
    ('swift', 'Programming', ['Swift', 'Apple Swift']),
    ('kotlin', 'Programming', ['Kotlin']),
    ('scala', 'Programming', ['Scala']),
    ('r', 'Programming', ['R', 'R Programming', 'R Language']),
    ('matlab', 'Programming', ['MATLAB', 'Matlab']),
    ('perl', 'Programming', ['Perl']),
    ('shell', 'Programming', ['Shell', 'Bash', 'Shell Scripting', 'bash']),
    ('sql', 'Programming', ['SQL', 'Structured Query Language']),
    ('dart', 'Programming', ['Dart']),
    ('lua', 'Programming', ['Lua']),
    ('haskell', 'Programming', ['Haskell']),
    ('elixir', 'Programming', ['Elixir']),
    ('clojure', 'Programming', ['Clojure']),

    # Frontend Frameworks
    ('react', 'Frontend', ['React', 'React.js', 'ReactJS', 'react.js']),
    ('vue', 'Frontend', ['Vue', 'Vue.js', 'VueJS', 'vue.js', 'Vue 3']),
    ('angular', 'Frontend', ['Angular', 'AngularJS', 'Angular 2+', 'angular']),
    ('svelte', 'Frontend', ['Svelte', 'SvelteKit']),
    ('nextjs', 'Frontend', ['Next.js', 'NextJS', 'Next', 'next.js']),
    ('nuxtjs', 'Frontend', ['Nuxt.js', 'NuxtJS', 'Nuxt', 'nuxt.js']),
    ('remix', 'Frontend', ['Remix', 'Remix.run']),
    ('gatsby', 'Frontend', ['Gatsby', 'GatsbyJS']),
    ('html', 'Frontend', ['HTML', 'HTML5']),
    ('css', 'Frontend', ['CSS', 'CSS3']),
    ('sass', 'Frontend', ['Sass', 'SCSS', 'SASS']),
    ('tailwind', 'Frontend', ['Tailwind CSS', 'TailwindCSS', 'Tailwind']),
    ('bootstrap', 'Frontend', ['Bootstrap', 'Bootstrap 5']),
    ('jquery', 'Frontend', ['jQuery', 'JQuery']),
    ('redux', 'Frontend', ['Redux', 'Redux Toolkit', 'RTK']),
    ('webpack', 'Frontend', ['Webpack', 'webpack']),
    ('vite', 'Frontend', ['Vite', 'vite']),

    # Backend Frameworks
    ('django', 'Backend', ['Django', 'django-rest-framework', 'DRF', 'Django REST']),
    ('flask', 'Backend', ['Flask']),
    ('fastapi', 'Backend', ['FastAPI', 'Fast API']),
    ('express', 'Backend', ['Express', 'Express.js', 'ExpressJS']),
    ('nodejs', 'Backend', ['Node.js', 'NodeJS', 'Node', 'node.js']),
    ('spring', 'Backend', ['Spring', 'Spring Boot', 'Spring Framework']),
    ('rails', 'Backend', ['Ruby on Rails', 'Rails', 'RoR']),
    ('laravel', 'Backend', ['Laravel']),
    ('aspnet', 'Backend', ['ASP.NET', 'ASP.NET Core', '.NET', 'dotnet']),
    ('graphql', 'Backend', ['GraphQL', 'graphql']),
    ('rest-api', 'Backend', ['REST API', 'RESTful', 'REST', 'RESTful API']),
    ('grpc', 'Backend', ['gRPC', 'GRPC']),

    # Databases
    ('postgresql', 'Database', ['PostgreSQL', 'Postgres', 'psql', 'PG']),
    ('mysql', 'Database', ['MySQL', 'mysql', 'MariaDB']),
    ('mongodb', 'Database', ['MongoDB', 'Mongo', 'mongo']),
    ('redis', 'Database', ['Redis', 'redis']),
    ('elasticsearch', 'Database', ['Elasticsearch', 'Elastic Search', 'ES']),
    ('sqlite', 'Database', ['SQLite', 'sqlite3']),
    ('dynamodb', 'Database', ['DynamoDB', 'Dynamo DB', 'AWS DynamoDB']),
    ('cassandra', 'Database', ['Cassandra', 'Apache Cassandra']),
    ('neo4j', 'Database', ['Neo4j', 'Neo4J']),
    ('firebase', 'Database', ['Firebase', 'Firestore', 'Firebase Realtime DB']),
    ('supabase', 'Database', ['Supabase']),

    # Cloud & DevOps
    ('aws', 'Cloud', ['AWS', 'Amazon Web Services']),
    ('azure', 'Cloud', ['Azure', 'Microsoft Azure']),
    ('gcp', 'Cloud', ['GCP', 'Google Cloud', 'Google Cloud Platform']),
    ('docker', 'DevOps', ['Docker', 'docker', 'Containerization']),
    ('kubernetes', 'DevOps', ['Kubernetes', 'K8s', 'k8s']),
    ('terraform', 'DevOps', ['Terraform', 'terraform', 'IaC']),
    ('ansible', 'DevOps', ['Ansible']),
    ('jenkins', 'DevOps', ['Jenkins']),
    ('github-actions', 'DevOps', ['GitHub Actions', 'GH Actions']),
    ('gitlab-ci', 'DevOps', ['GitLab CI', 'GitLab CI/CD']),
    ('circleci', 'DevOps', ['CircleCI', 'Circle CI']),
    ('nginx', 'DevOps', ['Nginx', 'NGINX']),
    ('linux', 'DevOps', ['Linux', 'Ubuntu', 'CentOS', 'Debian']),
    ('git', 'DevOps', ['Git', 'git', 'GitHub', 'GitLab', 'Bitbucket']),
    ('ci-cd', 'DevOps', ['CI/CD', 'Continuous Integration', 'Continuous Deployment']),

    # Data Science & ML
    ('machine-learning', 'Data Science', ['Machine Learning', 'ML', 'machine learning']),
    ('deep-learning', 'Data Science', ['Deep Learning', 'DL', 'Neural Networks']),
    ('tensorflow', 'Data Science', ['TensorFlow', 'Tensorflow', 'TF']),
    ('pytorch', 'Data Science', ['PyTorch', 'pytorch']),
    ('scikit-learn', 'Data Science', ['scikit-learn', 'sklearn', 'Scikit-Learn']),
    ('pandas', 'Data Science', ['Pandas', 'pandas']),
    ('numpy', 'Data Science', ['NumPy', 'numpy']),
    ('data-analysis', 'Data Science', ['Data Analysis', 'Data Analytics']),
    ('data-visualization', 'Data Science', ['Data Visualization', 'Data Viz']),
    ('nlp', 'Data Science', ['NLP', 'Natural Language Processing']),
    ('computer-vision', 'Data Science', ['Computer Vision', 'CV', 'Image Recognition']),
    ('llm', 'Data Science', ['LLM', 'Large Language Models', 'GPT', 'Generative AI']),
    ('spark', 'Data Science', ['Apache Spark', 'PySpark', 'Spark']),
    ('tableau', 'Data Science', ['Tableau']),
    ('power-bi', 'Data Science', ['Power BI', 'PowerBI']),
    ('jupyter', 'Data Science', ['Jupyter', 'Jupyter Notebook']),
    ('statistics', 'Data Science', ['Statistics', 'Statistical Analysis']),

    # Mobile
    ('react-native', 'Mobile', ['React Native', 'RN', 'react-native']),
    ('flutter', 'Mobile', ['Flutter', 'Dart/Flutter']),
    ('ios', 'Mobile', ['iOS', 'iOS Development', 'iPhone Development']),
    ('android', 'Mobile', ['Android', 'Android Development']),
    ('swiftui', 'Mobile', ['SwiftUI']),
    ('kotlin-multiplatform', 'Mobile', ['Kotlin Multiplatform', 'KMP', 'KMM']),

    # Design
    ('figma', 'Design', ['Figma']),
    ('sketch', 'Design', ['Sketch']),
    ('adobe-xd', 'Design', ['Adobe XD', 'XD']),
    ('photoshop', 'Design', ['Photoshop', 'Adobe Photoshop']),
    ('illustrator', 'Design', ['Illustrator', 'Adobe Illustrator']),
    ('ui-design', 'Design', ['UI Design', 'User Interface Design']),
    ('ux-design', 'Design', ['UX Design', 'User Experience Design', 'UX']),
    ('ux-research', 'Design', ['UX Research', 'User Research']),
    ('design-systems', 'Design', ['Design Systems']),
    ('prototyping', 'Design', ['Prototyping', 'Wireframing']),

    # Project Management / Soft Skills
    ('agile', 'Management', ['Agile', 'Agile Methodology', 'Scrum', 'Kanban']),
    ('project-management', 'Management', ['Project Management', 'PM']),
    ('product-management', 'Management', ['Product Management', 'Product Owner', 'PO']),
    ('jira', 'Management', ['Jira', 'JIRA', 'Atlassian Jira']),
    ('leadership', 'Management', ['Leadership', 'Team Leadership', 'People Management']),
    ('communication', 'Soft Skills', ['Communication', 'Written Communication']),
    ('problem-solving', 'Soft Skills', ['Problem Solving', 'Analytical Thinking']),
    ('teamwork', 'Soft Skills', ['Teamwork', 'Collaboration', 'Team Player']),

    # Testing / QA
    ('testing', 'Testing', ['Testing', 'Software Testing', 'QA']),
    ('unit-testing', 'Testing', ['Unit Testing', 'Unit Tests']),
    ('jest', 'Testing', ['Jest']),
    ('pytest', 'Testing', ['pytest', 'Pytest']),
    ('selenium', 'Testing', ['Selenium', 'Selenium WebDriver']),
    ('cypress', 'Testing', ['Cypress', 'cypress']),
    ('playwright', 'Testing', ['Playwright']),
    ('tdd', 'Testing', ['TDD', 'Test-Driven Development']),

    # Security
    ('cybersecurity', 'Security', ['Cybersecurity', 'Cyber Security', 'InfoSec']),
    ('penetration-testing', 'Security', ['Penetration Testing', 'Pen Testing', 'Ethical Hacking']),
    ('oauth', 'Security', ['OAuth', 'OAuth 2.0', 'OAuth2']),
    ('jwt', 'Security', ['JWT', 'JSON Web Tokens']),
    ('encryption', 'Security', ['Encryption', 'Cryptography']),

    # Marketing / Business
    ('seo', 'Marketing', ['SEO', 'Search Engine Optimization']),
    ('google-analytics', 'Marketing', ['Google Analytics', 'GA4']),
    ('content-marketing', 'Marketing', ['Content Marketing']),
    ('social-media-marketing', 'Marketing', ['Social Media Marketing', 'SMM']),
    ('email-marketing', 'Marketing', ['Email Marketing']),
    ('copywriting', 'Marketing', ['Copywriting', 'Content Writing']),
    ('digital-marketing', 'Marketing', ['Digital Marketing']),

    # Miscellaneous
    ('api-design', 'Architecture', ['API Design', 'API Development']),
    ('microservices', 'Architecture', ['Microservices', 'Micro Services']),
    ('system-design', 'Architecture', ['System Design', 'Systems Architecture']),
    ('serverless', 'Architecture', ['Serverless', 'Lambda', 'Cloud Functions']),
    ('event-driven', 'Architecture', ['Event-Driven Architecture', 'EDA']),
    ('websocket', 'Architecture', ['WebSocket', 'WebSockets', 'Real-time']),
    ('blockchain', 'Emerging', ['Blockchain', 'Web3', 'Smart Contracts']),
    ('ar-vr', 'Emerging', ['AR/VR', 'Augmented Reality', 'Virtual Reality', 'XR']),
    ('iot', 'Emerging', ['IoT', 'Internet of Things']),
    ('robotics', 'Emerging', ['Robotics', 'Robot Programming']),
    ('game-development', 'Emerging', ['Game Development', 'Unity', 'Unreal Engine']),
]

# Build a fast lookup: alias → canonical_name  (computed at import time)
ALIAS_TO_CANONICAL = {}
for _canonical, _category, _aliases in INITIAL_SKILLS:
    ALIAS_TO_CANONICAL[_canonical.lower()] = _canonical
    for _alias in _aliases:
        ALIAS_TO_CANONICAL[_alias.lower()] = _canonical

# Category → list of canonical names
CATEGORY_SKILLS = {}
for _canonical, _category, _ in INITIAL_SKILLS:
    CATEGORY_SKILLS.setdefault(_category, []).append(_canonical)
