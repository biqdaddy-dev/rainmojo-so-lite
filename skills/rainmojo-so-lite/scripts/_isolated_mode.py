"""Put the user site-packages back when a script runs under ``python -I``.

Claude Code tells agents to run Python with ``-I`` when it reads downloaded
files, so a planted ``json.py`` in the data folder cannot run on import. ``-I``
also leaves out the user site-packages, which is where ``pip install --user``
puts ``requests``, ``beautifulsoup4`` and ``lxml``. The plugin's scripts then
stopped with "Missing dependency" and the agent skipped the step: 26 of the 30
so-audit baseline runs (DP-024, 2026-10-31) lost a step this way (RSO-012).

Each script puts its own folder on ``sys.path`` and imports this module before
any third-party or sibling import. Only two things come back: the plugin's
own scripts folder and the user's own site-packages. The current directory,
the one ``-I`` protects, stays off the path, and so do PYTHON* variables.
"""

import site
import sys

if sys.flags.isolated:
    site.addsitedir(site.getusersitepackages())
