# ---------------------------------------------------------------------------
# Comprehensive skills database with alias / synonym mapping.
#
# SKILLS_DB   – canonical list of skills used for matching.
# SKILL_ALIASES – maps common abbreviations / variations to the canonical form
#                 so that "reactjs" in a resume matches "react" in a JD (and
#                 vice-versa).
# ---------------------------------------------------------------------------

# ---- Canonical skills (lowercase, sorted) ----
SKILLS_DB = sorted(set(s.lower().strip() for s in [
    # Programming languages
    "python", "java", "c", "c++", "c#", "javascript", "typescript", "php", "ruby",
    "go", "golang", "swift", "kotlin", "r", "matlab", "scala", "rust", "dart",
    "sql", "html", "css", "bash", "shell scripting", "perl", "lua", "haskell",
    "elixir", "clojure", "objective-c", "groovy", "vba", "fortran", "cobol",
    "assembly", "solidity",

    # Web / frameworks
    "react", "react.js", "angular", "angularjs", "vue", "vue.js", "svelte",
    "node.js", "nodejs", "express", "express.js", "django", "flask", "fastapi",
    "spring boot", "spring", "spring mvc", "asp.net", ".net", ".net core",
    "next.js", "nuxt.js", "gatsby", "remix", "bootstrap", "tailwind",
    "tailwind css", "material ui", "jquery", "rest api", "restful api",
    "graphql", "websockets", "socket.io", "webpack", "vite", "babel",
    "sass", "scss", "less", "redux", "vuex", "pinia", "zustand",
    "storybook", "three.js", "d3.js", "electron",

    # Data / ML / AI
    "machine learning", "deep learning", "data science", "data analysis",
    "data engineering", "data analytics", "artificial intelligence", "ai",
    "nlp", "natural language processing", "computer vision", "generative ai",
    "large language models", "llm", "llms", "prompt engineering",
    "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn",
    "pandas", "numpy", "scipy", "matplotlib", "seaborn", "plotly",
    "opencv", "hugging face", "transformers", "langchain",
    "big data", "hadoop", "spark", "apache spark", "pyspark",
    "kafka", "apache kafka", "airflow", "apache airflow",
    "power bi", "tableau", "looker", "qlik", "data visualization",
    "statistics", "regression", "classification", "clustering",
    "neural networks", "cnn", "rnn", "lstm", "transformer",
    "reinforcement learning", "feature engineering", "model deployment",
    "mlops", "data pipelines", "etl", "elt",
    "random forest", "xgboost", "lightgbm", "svm",
    "a/b testing", "hypothesis testing", "bayesian statistics",
    "time series", "anomaly detection", "recommendation systems",

    # Databases
    "mysql", "postgresql", "postgres", "mongodb", "sqlite", "oracle",
    "sql server", "microsoft sql server", "redis", "firebase",
    "dynamodb", "cassandra", "couchdb", "neo4j", "mariadb",
    "elasticsearch", "opensearch", "influxdb", "supabase",
    "database design", "database management", "data modeling",
    "data warehousing", "snowflake", "redshift", "bigquery",
    "google bigquery",

    # Cloud / DevOps / Infrastructure
    "aws", "amazon web services", "azure", "microsoft azure",
    "google cloud", "google cloud platform", "gcp",
    "docker", "kubernetes", "k8s", "podman",
    "ci/cd", "cicd", "continuous integration", "continuous deployment",
    "jenkins", "github actions", "gitlab ci", "circleci", "travis ci",
    "terraform", "ansible", "puppet", "chef", "pulumi",
    "cloudformation", "arm templates",
    "linux", "unix", "windows server", "ubuntu",
    "git", "github", "gitlab", "bitbucket", "svn",
    "devops", "sre", "site reliability engineering",
    "microservices", "serverless", "lambda", "cloud functions",
    "api gateway", "load balancing", "nginx", "apache",
    "monitoring", "prometheus", "grafana", "datadog", "new relic",
    "splunk", "elk stack", "logging",
    "infrastructure as code", "iac",
    "helm", "istio", "service mesh",
    "vagrant", "virtualbox", "vmware",

    # Mobile
    "android", "ios", "flutter", "react native", "swiftui",
    "xamarin", "ionic", "cordova", "kotlin multiplatform",
    "mobile development", "app development",

    # Software engineering practices
    "object oriented programming", "oop", "functional programming",
    "data structures", "algorithms", "design patterns",
    "solid principles", "clean code", "clean architecture",
    "agile", "scrum", "kanban", "jira", "confluence",
    "unit testing", "integration testing", "end to end testing",
    "test driven development", "tdd", "bdd",
    "behavior driven development",
    "software architecture", "system design", "api development",
    "api design", "debugging", "code review", "version control",
    "pair programming", "continuous improvement",
    "technical documentation", "swagger", "openapi",
    "junit", "pytest", "jest", "mocha", "cypress", "selenium",
    "playwright", "postman", "soapui",

    # Cybersecurity
    "cybersecurity", "information security", "network security",
    "application security", "cloud security",
    "penetration testing", "ethical hacking", "vulnerability assessment",
    "cryptography", "encryption",
    "siem", "soc", "incident response", "threat modeling",
    "owasp", "compliance", "gdpr", "hipaa", "pci dss",
    "identity management", "iam", "oauth", "jwt", "saml",
    "zero trust", "firewall", "vpn", "ids", "ips",
    # Cybersecurity tools / practical skills (added: earlier vocabulary only
    # covered generic/managerial security terms, missing hands-on tools that
    # commonly appear on real cybersecurity resumes and JDs)
    "nmap", "wireshark", "kali linux", "pfsense", "suricata",
    "reverse engineering", "steganography", "web exploitation",
    "digital forensics", "iptables", "ssh", "dmz", "ctf",
    "firewall configuration",

    # Networking
    "vlan", "dhcp", "nat", "acl", "ospf", "rip", "inter vlan routing",
    "subnetting", "tcp/ip networking", "routing protocols",

    # Business / management
    "project management", "product management", "program management",
    "business analysis", "business intelligence",
    "requirement gathering", "requirements analysis",
    "stakeholder management", "risk management", "change management",
    "budgeting", "forecasting", "strategic planning",
    "market research", "competitive analysis",
    "digital marketing", "seo", "sem", "ppc",
    "content marketing", "social media marketing", "email marketing",
    "google analytics", "google ads",
    "sales", "business development", "account management",
    "crm", "salesforce", "hubspot",
    "excel", "microsoft excel", "google sheets",
    "financial analysis", "financial modeling", "accounting",
    "supply chain management", "operations management",
    "lean", "six sigma",

    # Design
    "ui/ux", "ux research",
    "figma", "adobe xd", "sketch", "invision",
    "photoshop", "adobe photoshop", "illustrator", "adobe illustrator",
    "after effects", "premiere pro", "canva",
    "graphic design", "visual design", "interaction design",
    "wireframing", "prototyping", "usability testing",
    "responsive design", "accessibility", "wcag",
    "design systems", "design thinking",

    # Soft skills
    "communication", "written communication", "verbal communication",
    "teamwork", "leadership", "people management",
    "problem solving", "critical thinking", "analytical thinking",
    "time management", "organizational skills",
    "adaptability", "creativity", "innovation",
    "collaboration", "cross functional collaboration",
    "presentation skills", "public speaking",
    "negotiation", "conflict resolution", "decision making",
    "attention to detail", "customer service", "client management",
    "mentoring", "coaching", "training",
    "emotional intelligence", "interpersonal skills",
    "remote work", "self motivated", "initiative",

    # Emerging / specialized
    "blockchain", "web3", "smart contracts", "defi",
    "iot", "internet of things", "embedded systems",
    "robotics", "ros", "arduino", "raspberry pi",
    "quantum computing", "augmented reality", "ar",
    "virtual reality", "vr", "mixed reality",
    "game development", "unity", "unreal engine",
    "3d modeling", "blender",
    "natural language understanding", "nlu",
    "speech recognition", "chatbot", "conversational ai",
    "edge computing", "fog computing",
    "5g", "networking", "tcp/ip", "dns", "http",
]))


# ---------------------------------------------------------------------------
# Alias / synonym map: variation -> canonical form
# When we see an alias in text, we treat it as finding the canonical skill.
# ---------------------------------------------------------------------------

SKILL_ALIASES = {}
_alias_raw = {
    # JavaScript ecosystem
    "js":               "javascript",
    "es6":              "javascript",
    "es2015":           "javascript",
    "ecmascript":       "javascript",
    "ts":               "typescript",
    "reactjs":          "react",
    "react js":         "react",
    "react.js":         "react",
    "angularjs":        "angular",
    "angular.js":       "angular",
    "angular js":       "angular",
    "vuejs":            "vue",
    "vue js":           "vue",
    "vue.js":           "vue",
    "sveltejs":         "svelte",
    "nextjs":           "next.js",
    "next js":          "next.js",
    "nuxtjs":           "nuxt.js",
    "nuxt js":          "nuxt.js",
    "expressjs":        "express",
    "express js":       "express",
    "express.js":       "express",
    "nodejs":           "node.js",
    "node js":          "node.js",
    "node":             "node.js",
    "deno":             "node.js",

    # Python ecosystem
    "py":               "python",
    "python3":          "python",
    "sklearn":          "scikit-learn",
    "sci-kit learn":    "scikit-learn",
    "scikit learn":     "scikit-learn",
    "tf":               "tensorflow",
    "keras":            "keras",
    "torch":            "pytorch",

    # C-family
    "c sharp":          "c#",
    "csharp":           "c#",
    "c plus plus":      "c++",
    "cpp":              "c++",
    "obj-c":            "objective-c",
    "objc":             "objective-c",

    # Go
    "go lang":          "golang",
    "go language":      "golang",

    # Databases
    "postgres":         "postgresql",
    "psql":             "postgresql",
    "mongo":            "mongodb",
    "mongo db":         "mongodb",
    "mssql":            "sql server",
    "ms sql":           "sql server",
    "ms sql server":    "sql server",
    "dynamo db":        "dynamodb",
    "dynamo":           "dynamodb",
    "elastic search":   "elasticsearch",

    # Cloud
    "amazon web services":  "aws",
    "microsoft azure":      "azure",
    "google cloud platform": "gcp",
    "google cloud":         "gcp",
    "gc":                   "gcp",

    # DevOps
    "k8s":              "kubernetes",
    "kube":             "kubernetes",
    "container":        "docker",
    "containers":       "docker",
    "containerization": "docker",
    "ci cd":            "ci/cd",
    "cicd":             "ci/cd",
    "continuous integration": "ci/cd",
    "continuous deployment":  "ci/cd",
    "continuous delivery":    "ci/cd",
    "gh actions":       "github actions",
    "infrastructure as code": "terraform",
    "iac":              "terraform",

    # AI / ML
    "ml":               "machine learning",
    "dl":               "deep learning",
    "gen ai":           "generative ai",
    "genai":            "generative ai",
    "large language model":  "llm",
    "large language models": "llm",
    "llms":             "llm",
    "natural language processing": "nlp",
    "computer vision":  "computer vision",
    "cv":               "computer vision",
    "convolutional neural network": "cnn",
    "recurrent neural network":     "rnn",

    # Data
    "bi":               "business intelligence",
    "powerbi":          "power bi",
    "power-bi":         "power bi",
    "big query":        "bigquery",

    # Mobile
    "react-native":     "react native",
    "rn":               "react native",
    "kotlin mp":        "kotlin multiplatform",
    "kmp":              "kotlin multiplatform",

    # Security
    "infosec":          "information security",
    "appsec":           "application security",
    "pen testing":      "penetration testing",
    "pen test":         "penetration testing",
    "pentest":          "penetration testing",
    "kali":             "kali linux",
    "suricata ids":     "suricata",
    "acls":             "acl",
    "access control list": "acl",
    "access control lists": "acl",
    "vlans":            "vlan",
    "vlan configuration": "vlan",
    "inter-vlan routing": "inter vlan routing",
    "intervlan routing": "inter vlan routing",
    "capture the flag": "ctf",
    "network analysis":  "network security",

    # Design -- all these phrasings mean the same underlying skill, so they
    # all resolve to one canonical instead of splintering into three
    # different "skills" that then can't recognize each other.
    "ui ux":                    "ui/ux",
    "uiux":                     "ui/ux",
    "ui-ux":                    "ui/ux",
    "ui design":                "ui/ux",
    "ux design":                "ui/ux",
    "user interface design":    "ui/ux",
    "user experience design":   "ui/ux",
    "user experience":          "ui/ux",
    "user interface":           "ui/ux",

    # Practices
    "oop":              "object oriented programming",
    "oops":             "object oriented programming",
    "dsa":              "data structures",
    "ds and algo":      "data structures",
    "rest":             "rest api",
    "restful":          "rest api",
    "restful api":      "rest api",
    "rest apis":        "rest api",

    # Management / process
    "pm":               "project management",
    "pmp":              "project management",
    "product mgmt":     "product management",
    "sdlc":             "agile",
    "waterfall":        "agile",
    "system architecture": "software architecture",
    "ms excel":         "excel",
    "microsoft excel":  "excel",
    "google sheet":     "google sheets",
    "crm":              "salesforce",

    # Misc
    "shell":            "bash",
    "sh":               "bash",
    "zsh":              "bash",
    "powershell":       "bash",
    
    # Soft skills variations
    "communicated":     "communication",
    "communicating":    "communication",
    "collaborate":      "collaboration",
    "collaborated":     "collaboration",
    "collaborating":    "collaboration",
    "team player":      "teamwork",
    
    # LLM variations
    "fine-tuning llms": "llm fine tuning",
    "fine tuning llms": "llm fine tuning",
    "model fine-tuning": "llm fine tuning",
    "llm applications": "llm application development",
    "rag": "llm application development",
    "retrieval-augmented generation": "llm application development",
    
}

for alias, canonical in _alias_raw.items():
    SKILL_ALIASES[alias.lower().strip()] = canonical.lower().strip()

# Normalize once and filter out any keys that exist as aliases to prevent duplicate chips (e.g. llms & large language models)
SKILLS_DB.extend(["openai api", "openai", "ocr", "paddleocr", "gpt chatbot", "llm fine tuning", "llm application development", "ai development"])
SKILLS_DB = sorted(list(set(s.lower().strip() for s in SKILLS_DB if s.lower().strip() not in SKILL_ALIASES)))

# ---------------------------------------------------------------------------
# Implied-skill map: canonical_skill -> set of specific tools/practices that,
# on their own, are solid direct evidence the person has that broader skill.
#
# This exists because SKILLS_DB/SKILL_ALIASES intentionally keep specific
# tools (e.g. "git", "opencv") and the broader skill/practice they belong to
# (e.g. "version control", "computer vision") as separate canonical entries
# -- collapsing them into one alias would lose the distinction when a JD or
# resume genuinely wants the specific tool named. But that means a resume
# which only ever says "Git" and "GitHub" will never literally contain the
# string "version control", and relies entirely on the semantic-embedding
# fallback to bridge the gap. If that model isn't available (no internet on
# first run, package not installed, etc.) or simply doesn't score two short
# phrases high enough, the broader skill gets wrongly flagged as missing
# even though it's clearly demonstrated. This map is a safety net for that.
# ---------------------------------------------------------------------------
SKILL_IMPLIES = {
    "version control": {"git", "github", "gitlab", "bitbucket", "svn"},
    "git": {"github", "gitlab", "bitbucket"},
    "computer vision": {"opencv"},
    "agile": {"scrum", "kanban"},
    "ui/ux": {"figma", "sketch", "adobe xd", "invision", "wireframing", "prototyping", "usability testing"},
    "unit testing": {"junit", "pytest", "jest", "mocha", "cypress", "selenium", "playwright"},
    "ci/cd": {"jenkins", "github actions", "gitlab ci", "circleci", "travis ci"},
    "containerization": {"docker", "kubernetes", "podman"},
    "database management": {"mysql", "postgresql", "mongodb", "sqlite", "oracle", "redis"},
    "rest api": {"flask", "express", "express.js", "django", "fastapi", "spring boot",
                 "spring", "node.js", "asp.net", ".net"},
    "vulnerability assessment": {"nmap", "penetration testing", "ethical hacking", "suricata"},
    "system design": {"software architecture"},
    "networking": {"vlan", "dhcp", "nat", "acl", "ospf", "rip", "dns", "network security",
                   "inter vlan routing", "subnetting"},
    "mobile development": {"android", "ios", "kotlin", "swift", "swiftui", "flutter",
                            "react native", "xamarin", "ionic", "cordova",
                            "kotlin multiplatform"},
    "app development": {"android", "ios", "kotlin", "swift", "swiftui", "flutter",
                         "react native", "xamarin", "ionic", "cordova",
                         "kotlin multiplatform"},
}

# ---------------------------------------------------------------------------
# Weak-implied-skill map: canonical_skill -> set of *related but distinct*
# practices/skills that, on their own, are NOT direct evidence of the skill
# (unlike SKILL_IMPLIES above) but are close enough that a human reviewer
# would flag it as "worth clarifying" rather than a confirmed gap.
#
# Example: a JD asking for "Scrum" when the resume only says "Agile" (or
# vice versa). These terms are often used loosely/interchangeably in
# real-world resumes (particularly student/academic ones describing
# informal team process), but naming one is not proof of hands-on
# experience with the other -- so this deliberately produces the "weak"
# tier (worth clarifying) rather than a full/implied match.
# ---------------------------------------------------------------------------
SKILL_IMPLIES_WEAK = {
    "scrum": {"agile", "kanban"},
    "agile": {"scrum", "kanban", "waterfall"},
    "kanban": {"agile", "scrum"},
}


# Soft skills set
SOFT_SKILLS = {
    "communication", "written communication", "verbal communication",
    "teamwork", "leadership", "people management", "problem solving",
    "critical thinking", "analytical thinking", "time management",
    "organizational skills", "adaptability", "creativity", "innovation",
    "collaboration", "cross functional collaboration", "presentation skills",
    "public speaking", "negotiation", "conflict resolution", "decision making",
    "attention to detail", "customer service", "client management",
    "mentoring", "coaching", "training", "emotional intelligence",
    "interpersonal skills", "remote work", "self motivated", "initiative"
}

# NOTE: The old static SKILL_WEIGHTS importance table and the
# SEMANTIC_PARTIAL_MATCHES hand-written synonym dictionary used to live here.
# Both were hardcoded human judgment calls (e.g. deciding by hand that
# "python" matters more than "html", or that "teamwork" is a synonym of
# "collaboration"). They've been replaced in matcher.py by:
#   - a local sentence-embedding model (utils/semantic_model.py) that judges
#     semantic closeness between any two skill phrases, and
#   - a per-JD dynamic weight computed from how *this* job description
#     actually mentions each skill (frequency + position), rather than a
#     fixed global ranking of which skills are "important".
# SKILLS_DB, SKILL_ALIASES, and SOFT_SKILLS below remain as a vocabulary used
# only to *extract* candidate skill terms from free text -- that's a
# taxonomy, not a verdict, and is still needed since there's no offline NER
# model in scope here.

