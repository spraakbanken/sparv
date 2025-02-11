#!/usr/bin/env bash
# set -x

# Script for creating PDFs from markdown
# Requires markdown, latex and Python pandocfilters

USER_MANUAL_FILES=$(grep -P 'user-manual/.*\.md' ../mkdocs.yml -o | grep -v 'intro\.md' | sed 's/^/..\//')

DEVELOPERS_GUIDE_FILES=$(grep -P 'developers-guide/.*\.md' ../mkdocs.yml -o | sed 's/^/..\//')

# Get version number from sparv/__init__.py
SPARV_VERSION=$(grep -P '(?<=__version__ = ").+(?=")' -o ../../sparv/__init__.py)

function make_pandoc {
    # Convert markdown to latex/pdf:
    # pandoc -t latex -o $1.tex $1.md \
    # pandoc -t native $1.md \
    pandoc -t latex -o $1.pdf $1.md \
    --filter filter.py \
    -H settings_template.tex `# include in header` \
    --template template.tex `# use template`  \
    --toc `# table of contents` \
    -N `# numbered sections` \
    -V urlcolor=RoyalBlue `# color links blue` \
    --listings `# use listings package for LaTeX code blocks`
    #-V links-as-notes=true `# print links as footnotes` \
}


function make_document {
    # $1: file name (without extension)
    # $2: markdown file list
    # $3: Title string

    HEADER="
---
title: Sparv $SPARV_VERSION - $3
author: |
  | Språkbanken Text
  | Institutionen för svenska, flerspråkighet och språkteknologi
  | Göteborgs universitet
  |
  |
  |
  |
  | ![](../images/sparv_detailed.png){width=2.5cm}
---
    "

    # Concat header and files
    echo -e "$HEADER" > $1.md
    for f in $2
    do
      cat $f >> $1.md
      echo -e "\n" >> $1.md
    done
    make_pandoc $1

    # Make GU-ISS publication without header
    for f in $2
    do
      cat $f >> GU-ISS-$1.md
      echo -e "\n" >> GU-ISS-$1.md
    done
    make_pandoc GU-ISS-$1
}

# Make PDFs
make_document user-manual "$USER_MANUAL_FILES" "User Manual"
make_document developers-guide "$DEVELOPERS_GUIDE_FILES" "Developer's Guide"

# Clean-up
rm user-manual.md
rm developers-guide.md
rm GU-ISS-user-manual.md
rm GU-ISS-developers-guide.md
