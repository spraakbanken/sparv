# Requirements for Source Files

To ensure Sparv can process your corpus effectively, please ensure your source files meet the following requirements:

- If your corpus is in XML format, ensure your **XML is valid** and that the text to be analyzed is actual text (not
   attribute values).

- All source files must use the same file format, file extension, and (if applicable) the same markup.

- If your source files are very large or if your corpus consists of many small files, Sparv may become slow. Large files
   may also cause memory issues. Aim to keep each file between 5-10 MB. If you have many small files, consider combining
   them into larger files. If your machine has ample memory, processing larger files may be feasible.

- Do not manually create directories named `sparv-workdir` or `export` in your corpus directory, as these directories
  are reserved for Sparv, and their contents may be overwritten or deleted.
