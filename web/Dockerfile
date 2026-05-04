FROM python:3.12-slim

# Set working directory
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Allow 'from web.X import ...' to resolve — the project expects web/ as a package
RUN ln -s /app /web
ENV PYTHONPATH=/

# Expose the port Flask runs on
EXPOSE 5000

# Run the app
CMD ["python", "wsgi.py"]