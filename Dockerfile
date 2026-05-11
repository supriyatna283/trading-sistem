FROM python:3.11-slim

WORKDIR /app

# Copy requirements from backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# HuggingFace Spaces requires a non-root user (UID 1000)
RUN useradd -m -u 1000 user

# Ensure user has write access to the app directory (for data/ logs/ etc)
RUN chown -R user:user /app

USER user

# HF Spaces default port
EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
