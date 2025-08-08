# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install git, which is required to clone repositories
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y

# Clone the main ComfyUI repository
RUN git clone https://github.com/comfyanonymous/ComfyUI.git

# Install ComfyUI's Python dependencies
RUN pip install --no-cache-dir -r /app/ComfyUI/requirements.txt

# --- Install Custom Nodes ---
# Clone all the required custom nodes for your specific workflow
RUN cd /app/ComfyUI/custom_nodes && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git && \
    git clone https://github.com/city96/ComfyUI-GGUF.git && \
    git clone https://github.com/calcuis/gguf.git && \
    git clone https://github.com/rgthree/rgthree-comfy.git

RUN for req_file in $(find /app/ComfyUI/custom_nodes -type f -name "requirements.txt"); \
    do \
      echo "Installing requirements from $req_file"; \
      pip install --no-cache-dir -r "$req_file"; \
    done

# Install Python dependencies for our FastAPI wrapper
RUN pip install --no-cache-dir "fastapi[standard]" websocket-client requests
RUN pip install --no-cache-dir opencv-python gguf matplotlib

# Copy your wrapper script and the startup script into the container
COPY run_api.py .
COPY scripts/start.sh .

# Make the startup script executable
RUN chmod +x start.sh

# Expose the port the API will run on
EXPOSE 5528

# The command to run when the container starts
CMD ["./start.sh"]