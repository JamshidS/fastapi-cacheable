# Demo

1) Start Redis:

    docker compose -f examples/docker-compose.yml up -d

     If your Redis requires a password, either:

     - Set `REDIS_URL` with credentials:

             setx REDIS_URL "redis://:demo-password@localhost:6379/0"

         (start a new terminal after `setx`)

     - Or set `REDIS_URL` and `REDIS_PASSWORD` separately:

             setx REDIS_URL "redis://localhost:6379/0"
             setx REDIS_PASSWORD "demo-password"

2) Install deps:

    pip install -e .
    pip install fastapi uvicorn

3) Run the app:

    uvicorn examples.demo_fastapi_app:app --reload

   Or run directly:

    python examples/demo_fastapi_app.py

Try:
- GET  /users/1   (first call ~1s, next calls fast until TTL expires)
- POST /users/1/refresh
- DELETE /users/1
- DELETE /users/cache
