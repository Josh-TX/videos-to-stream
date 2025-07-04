FROM debian:bookworm

# Install Python 3 and required packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-gi \
    python3-gst-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
	gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY src/*.py /app/
COPY src/web /serve/

EXPOSE 8000
CMD ["bash", "-c", "python3 -u app/stream.py & python3 app/serve.py"]