# Runs the shared-feed multi-tenant POC on the RELEASED wheel (runnable today).
# The runtime add/remove feature needs a branch-built wheel — see BLOCKERS.md.
FROM python:3.14-slim

RUN pip install --no-cache-dir nautilus_trader==1.231.0 redis psutil

WORKDIR /poc
COPY feed.py tenant.py bench.py packed.py control_plane_demo.py ./

# Default: do nothing; compose overrides `command` per service.
CMD ["python", "-c", "print('override command in compose')"]
