FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY streamlit.py .

# Expose Streamlit port
EXPOSE 8501

# Create streamlit config directory
RUN mkdir -p ~/.streamlit

# Configure Streamlit
RUN echo "[server]\nheadless = true\nport = 8501\nenableCORS = false\n" > ~/.streamlit/config.toml

# Run Streamlit app
CMD ["streamlit", "run", "streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
