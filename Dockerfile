# The upload server, for a phone: pick a sheet, see it read-only.
# Built and run by CapRover (see captain-definition); nothing here is specific
# to it, though its app is set to send traffic to port 8000.
FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY gridly ./gridly
RUN pip install --no-cache-dir ".[web]"

# A session is a real process handling a file from outside, so not as root.
RUN useradd --create-home gridly
USER gridly

# Above 1024, which a user who is not root may listen on.
EXPOSE 8000
CMD ["gridly-web", "--uploads", "--host", "0.0.0.0", "--port", "8000"]
