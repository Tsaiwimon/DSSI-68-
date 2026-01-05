from pathlib import Path
import os
from dotenv import load_dotenv


# ---- Base & .env ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # โหลดตัวแปรจาก .env ตั้งแต่ต้นไฟล์

# ---- Core -------------------------------------------------------------------
SECRET_KEY = 'django-insecure-)wo&*ioi^w1%$qi3^&&s6%d#85shnt)@7a9z$1msz!76-dv@*c'
DEBUG = True

# อนุญาตทั้ง localhost และโดเมน ngrok (อย่าประกาศซ้ำด้านล่าง)
ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".ngrok-free.app"]

CSRF_TRUSTED_ORIGINS = ["https://*.ngrok-free.app"]


# ให้ CSRF เชื่อถือโดเมน ngrok ด้วย (สำคัญเวลา POST ฟอร์มผ่านโดเมน ngrok)
CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.app",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "dress.apps.DressConfig",
    'django_extensions',  
    'backoffice',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'dress_rental.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "dress.context_processors.unread_notifications",
                
            ],
        },
    },
]

WSGI_APPLICATION = 'dress_rental.wsgi.application'

# ---- Database ---------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'dress_rental',
        'USER': 'postgres',
        'PASSWORD': 'pass1234',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# ---- Auth -------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = "dress:login"
LOGIN_REDIRECT_URL = "dress:login_redirect"
LOGOUT_REDIRECT_URL = "dress:login"
# AUTH_USER_MODEL = 'dress.CustomUser'  # ถ้ายังไม่ใช้ให้คอมเมนต์ไว้

# ---- I18N / TZ --------------------------------------------------------------
LANGUAGE_CODE = 'th'
TIME_ZONE = 'Asia/Bangkok'
USE_I18N = True
USE_TZ = True

# ---- Static / Media ---------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",
    BASE_DIR / "static_img",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---- Omise (Sandbox/Test) ---------------------------------------------------
OMISE_PUBLIC_KEY = os.getenv("OMISE_PUBLIC_KEY", "")
OMISE_SECRET_KEY = os.getenv("OMISE_SECRET_KEY", "")
OMISE_CURRENCY   = os.getenv("OMISE_CURRENCY", "thb")
# หมายเหตุ: ใน view ให้ตั้งค่า omise.api_public / omise.api_secret จากตัวแปรข้างบน

# ---- Email ------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@localhost"






