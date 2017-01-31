In this directory you will find example fonts, tagged as "free for
personal use" by font providing websites. They have been converted
to PostScript, so they can be used as a proof-of-concept of PRET's
'cross' command.

To add custom fonts, just copy them into this directory. Note that
PRET (and targeted printers) only accepts PostScript fonts, so you
may need to convert them first, for example using the `ttfps' tool:

`./ttfps font.ttf font.ps`

The tool converts TrueType fonts to Type42. A copy can be obtained
from: https://www.irif.fr/~jch/software/files/ttfps-0.3.tar.gz
