# QuickCart Backend

FastAPI-based backend for QuickCart e-commerce platform.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis 6+


### Installation & Setup

Follow these steps to get your development environment ready:

1. **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/quickcart.git
    cd quickcart/backend
    ```
2. **Create a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3. **Install dependencies**
    ```bash
    make install
    ```
4. **Set up environment variables**
    ```bash
    cp .env.example .env
    # Edit .env with your configuration
    ```
5. **Initialize the database**
    ```bash
    make init-db
    make migrate
    make seed
    ```
6. **Run the development server**
    ```bash
    make dev
    ```
    The API will be available at http://localhost:8000

## 📚 API Documentation

Swagger UI: http://localhost:8000/api/docs
ReDoc: http://localhost:8000/api/redoc

## 🏗️ Project Structure
backend/
├── app/
│   ├── api/          # API routes
│   ├── core/         # Core functionality
│   ├── models/       # Database models
│   ├── services/     # Business logic
│   └── utils/        # Utilities
├── alembic/          # Database migrations
├── scripts/          # Utility scripts
├── tests/            # Test files
└── requirements.txt  # Dependencies

## 🧪 Testing
Run tests:
```bash
make test
```
Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

## 🚀 Deployment

### Using Docker

Build image:
```bash
make docker-build
```
Run container:
```bash
make docker-run
```

### Manual Deployment

Install dependencies:
```bash
pip install -r requirements.txt
```
Run migrations:
```bash
alembic upgrade head
```
Start server:
```bash
make run
```

## 🛠️ Development

### Code Formatting
```bash
make format
```
### Linting
```bash
make lint
```
### Create Migration
```bash
make migrate-create
```

## 📝 Environment Variables

| Variable           | Description                | Default                        |
|--------------------|---------------------------|---------------------------------|
| DATABASE_URL       | PostgreSQL connection URL | -                               |
| REDIS_URL          | Redis connection URL      | redis://localhost:6379          |
| SECRET_KEY         | JWT secret key            | -                               |
| RAZORPAY_KEY_ID    | Razorpay API key          | -                               |
| CLOUDINARY_CLOUD_NAME | Cloudinary cloud name   | -                               |

See `.env.example` for all variables.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License
This project is licensed under the MIT License.

---

This completes the entire backend implementation for the QuickCart application. The backend includes:

1. **Complete API Implementation**: All endpoints for authentication, products, cart, orders, payments, etc.
2. **Database Models**: Comprehensive models for all entities
3. **Services**: Business logic separated into service layers
4. **Security**: JWT authentication, role-based access control
5. **Caching**: Redis integration for performance
6. **File Storage**: Cloudinary integration
7. **Payment Gateway**: Razorpay integration
8. **Notifications**: Email and SMS services
9. **Testing Setup**: Pytest configuration
10. **Development Tools**: Makefile, Docker support
11. **Documentation**: Comprehensive README and API docs

The backend is production-ready with proper error handling, validation, logging, and monitoring support. It follows best practices for FastAPI development including:

- Async/await for all database operations
- Proper dependency injection
- Comprehensive error handling
- Input validation with Pydantic
- Database migrations with Alembic
- Modular architecture
- Clean separation of concerns
```
