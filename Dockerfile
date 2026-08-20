FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy the explicitly separate legacy Streamlit requirements
COPY requirements.txt requirements-streamlit.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-streamlit.txt

# Copy application files
COPY streamlit.py ./
COPY extension ./extension

# Expose Streamlit port
EXPOSE 8501

# Create streamlit config directory
RUN mkdir -p ~/.streamlit

# Configure Streamlit
RUN echo "[server]\nheadless = true\nport = 8501\nenableCORS = true\nenableXsrfProtection = true\n" > ~/.streamlit/config.toml

# Run Streamlit app
CMD ["streamlit", "run", "streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
