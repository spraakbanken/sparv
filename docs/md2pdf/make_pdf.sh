#!/usr/bin/env bash
set -euo pipefail  # Exit on error, unset variables, and pipe failures
IFS=$'\n\t'        # Set safe IFS

# Script for creating PDFs from markdown using Pandoc
# Requires markdown, pandoc, latex, and Python pandocfilters

# Get version number from sparv/__init__.py
SPARV_VERSION=$(grep -P '(?<=__version__ = ").+(?=")' -o ../../sparv/__init__.py)

# Title page for the PDF (not used in GU-ISS publication)
TITLEPAGE="
---
title: Sparv $SPARV_VERSION - Documentation
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

# Create output directory
OUTPUT_DIR="output"
mkdir -p "$OUTPUT_DIR"

# Function for converting markdown to pdf with Pandoc
function markdown_to_pdf {
    local input_file=$1
    local mode=$2

    case $mode in
        tex)
            # Convert to .tex for debugging
            pandoc -t latex -o "${OUTPUT_DIR}/${input_file}.tex" "${OUTPUT_DIR}/${input_file}.md"
            ;;
        pandoc)
            # Convert to pandoc's native format for debugging filters
            pandoc -t native "${OUTPUT_DIR}/${input_file}.md" -o "${OUTPUT_DIR}/${input_file}.pandoc"
            ;;
        pdf)
            # Convert markdown to latex/pdf
            pandoc -t latex -o "${OUTPUT_DIR}/${input_file}.pdf" "${OUTPUT_DIR}/${input_file}.md" \
                --filter filter.py \
                -H settings_template.tex `# include in header` \
                --template template.tex `# use template` \
                --toc `# table of contents` \
                --top-level-division=chapter `# treat top-level headings as chapters` \
                -N `# numbered sections` \
                -V urlcolor=RoyalBlue `# color links blue` \
                --listings `# use listings package for LaTeX code blocks`
            ;;
        *)
            echo "Invalid mode: $mode. Use 'tex', 'native', or 'pdf'."
            exit 1
            ;;
    esac
}

# Function to generate PDF with or without title page
function generate_pdf {
    local titlepage=$1
    local mode=$2
    local output_file

    # Define file mappings for the two parts of the documentation
    declare -A files=(
        ["user-manual.md"]="$(grep -P 'user-manual/.*\.md' ../mkdocs.yml -o | grep -v 'intro\.md' | sed 's/^/..\//')"
        ["dev-guide.md"]="$(grep -P 'developers-guide/.*\.md' ../mkdocs.yml -o | sed 's/^/..\//')"
    )

    # Concat files and shift headings for each document
    for output in "${!files[@]}"; do
        # Clear output file
        echo "" > "${OUTPUT_DIR}/${output}"
        for f in ${files[$output]}; do
            cat "$f" >> "${OUTPUT_DIR}/${output}"
            echo -e "\n" >> "${OUTPUT_DIR}/${output}"
        done
        pandoc "${OUTPUT_DIR}/${output}" --shift-heading-level-by=1 -o "${OUTPUT_DIR}/${output}"
    done

    # Add title page to the output file if needed
    if [ "$titlepage" = true ]; then
        output_file="sparv-documentation"
        echo -e "$TITLEPAGE" > "${OUTPUT_DIR}/${output_file}.md"
    else
        output_file="GU-ISS-sparv-documentation"
        echo "" > "${OUTPUT_DIR}/${output_file}.md"
    fi

    # Concatenate the user manual and developer's guide and convert to PDF
    echo -e "# User Manual\n" >> "${OUTPUT_DIR}/${output_file}.md"
    cat "${OUTPUT_DIR}/user-manual.md" >> "${OUTPUT_DIR}/${output_file}.md"
    echo "\newpage" >> "${OUTPUT_DIR}/${output_file}.md"
    echo -e "# Developer's Guide\n" >> "${OUTPUT_DIR}/${output_file}.md"
    cat "${OUTPUT_DIR}/dev-guide.md" >> "${OUTPUT_DIR}/${output_file}.md"

    # If MODE == md skip running pandoc
    if [ "$mode" = "md" ]; then
        return
    fi
    markdown_to_pdf "$output_file" "$mode"
}

# Parse command-line arguments
MODE="pdf"  # Default mode
while getopts "m:h" opt; do
    case $opt in
        m)
            MODE=$OPTARG
            ;;
        h)
            echo "Usage: $0 [-m mode] (mode: 'tex', 'pandoc', 'pdf')"
            echo "  -m mode   Specify the output format:"
            echo "            'tex'    Generate .tex files for debugging."
            echo "            'pandoc' Generate .pandoc files for debugging filters."
            echo "            'md'     Generate .md files."
            echo "            'pdf'    Generate PDF files (default)."
            echo "  -h        Display this help message."
            exit 0
            ;;
        *)
            echo "Invalid option. Use -h for help."
            exit 1
            ;;
    esac
done

# Generate PDFs (or .tex/.pandoc files) with and without title page
generate_pdf true "$MODE"
generate_pdf false "$MODE"

# Clean up intermediate files
if [ "$MODE" != "md" ]; then
    rm -f ${OUTPUT_DIR}/*.md
fi

# Print message about created files
echo "The following files have been created in the '${OUTPUT_DIR}' directory:"
case $MODE in
    tex)
        echo "- sparv-documentation.tex"
        echo "- GU-ISS-sparv-documentation.tex"
        ;;
    pandoc)
        echo "- sparv-documentation.pandoc"
        echo "- GU-ISS-sparv-documentation.pandoc"
        ;;
    md)
        echo "- sparv-documentation.md"
        echo "- GU-ISS-sparv-documentation.md"
        ;;
    pdf)
        echo "- sparv-documentation.pdf"
        echo "- GU-ISS-sparv-documentation.pdf"
        ;;
esac
