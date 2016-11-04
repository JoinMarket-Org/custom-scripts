# yield-generators
Different yield generators are collected here, which can replace joinmarket's default `yg-pe.py` if desired.

Each file beginning with "yg-" is a different one. Read the comment at the beginning of a yield generator's file to see what it is doing differently and what its intended purpose is.

To use one of these, copy the yg-file of your choice into your joinmarket-directoy, modify its default settings (optional) and start it just like you would start the default yield generator: `python yg-filename.py walletfilename.json` (or `python yg-filename.py --fast walletfilename.json` if you are restarting and want to sync the wallet faster).
