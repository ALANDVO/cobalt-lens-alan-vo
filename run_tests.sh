#!/bin/bash
cd /var/lib/alan-portfolio/workspaces/alan/cobalt-lens-alan-vo/backend
source venv/bin/activate
python -m pytest tests/ -v 2>&1
