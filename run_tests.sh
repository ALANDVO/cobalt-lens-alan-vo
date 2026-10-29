#!/bin/bash
cd /var/lib/alan-portfolio/workspaces/alan/cobalt-lens-alan-vo/backend
source venv/bin/activate
python -m pytest tests/test_parser.py -v 2>&1
