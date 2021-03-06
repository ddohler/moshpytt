** THIS PACKAGE IS NO LONGER MAINTAINED **
(and you probably should be using
[tesstrain.sh](https://github.com/tesseract-ocr/tesseract/blob/master/training/tesstrain.sh)
anyway)
These modifications to moshPyTT were made by Derek Dohler 

The original README file, written by John Beard, 
is below.

Changes from the original:

- Space, Return, and Enter now jump to the next box in the file
- Backspace now jumps to the previous box in the file
- Typing any character key immediately replaces the text of the current box
  with the corresponding character and then automatically jumps to the next box.
- Laptop arrow keys now work the same as number pad arrow keys.
- Added utility program mergeboxes.py that automatically merges nearby boxes. This may sometimes be helpful in correcting Tesseract's oversegmentation of characters.

==============================================================================
moshPyTT
==============================================================================

moshPyTT is a program to read, display and modify Tesseract boxfiles, which is
a crucial step when training Tesseract. It is intended to be faster and less
resource-intensive that previous programs.

Author:
    John Beard <john.j.beard at gmail.com>

It is based on pyTesseractTrainer, which in turn was based on
tesseractTrainer.py. The following people created those programs:
    Zdenko Podobný <zdenop at gmail.com>
    Mihail Radu Solcan (djvused and image maps)
    Cătălin Frâncu <cata at francu.com>

Autotrain.py is a utility script to take boxfile/image pairs and distill down
to a "traineddata" file, which is otherwise a long and tedious process.


Requirements
=====================

All scripts need Python:
* Python (2.6 works, lower versions probably work too)

moshPyTT:
 ** pyGTK (2.0 or higher)

Autotrain:
 ** Tesseract


Installation & Running
=====================

There is no installation.

    moshPyTT
    ============
    Run "python moshpytt.py [-i optional image name]" from any directory.

    Autotrain.py
    ============
    From the directory containing the boxfile/image pairs, run
    "...../moshpytt/autotrain.py"

    This is because the Tesseract tools only produce the files in the
    current working directory.

    You may need to run with elevated priveleges in order for the script to
    move the generated files to the "tessdata" directory if that directory is
    in a protected area (eg /usr/)

Copyright
=====================

This software is covered by the GNU General Public Licence
(version 3, or if you choose, a later version).

See the COPYING file in the root directory for the full licence.


Bugs and enhancements
=====================

If you have any enhancements, requests or bug reports, please file them in
bugzilla at:
  http://code.google.com/p/moshpytt/issues/list

If you would like to submit a patch, please create a diff (against the most
recent version, a *lot* of code can change between versions), and attach it to
the bug report. I would suggest creating a bug report before starting work so
I can hold off making changes that make merging your patch harder.


Getting help
=====================

If you need help with this software, it's probably because you found a bug. If
it seems like the problem you are having is a bug, please file an issue at the
URL in the "Bugs" section.

If you need other help, post an issue as it is likely others may have the same
problem
