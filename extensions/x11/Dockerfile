FROM base as x11
# Install X11 GUI support packages
RUN apt-get update && apt-get install -y \
    xauth x11-apps libgl1-mesa-glx libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*
