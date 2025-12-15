# How to View the ERD Diagram

## Quick Options:

### 1. **VS Code/Cursor Extension** (Easiest)
1. Open Cursor/VS Code
2. Install extension: **"Markdown Preview Mermaid Support"** by Matt Bierner
3. Open `ERD.md`
4. Press `Ctrl+Shift+V` (or `Cmd+Shift+V` on Mac) to open Markdown preview
5. The diagram will render automatically!

### 2. **Online Viewer** (No Installation)
1. Go to: https://mermaid.live/
2. Copy the Mermaid code block from `ERD.md` (lines 6-244)
3. Paste into the editor
4. View and export as PNG/SVG if needed

### 3. **GitHub/GitLab** (If you push to a repo)
- GitHub and GitLab automatically render Mermaid diagrams in markdown files
- Just push your `ERD.md` file and view it on the web

### 4. **Command Line Tool** (For generating images)
If you want to generate a PNG/SVG image:

```bash
# Install Node.js first, then:
npm install -g @mermaid-js/mermaid-cli

# Generate PNG image:
mmdc -i ERD.md -o ERD.png

# Generate SVG image:
mmdc -i ERD.md -o ERD.svg
```

### 5. **Browser Extensions**
- **Chrome/Edge**: "Mermaid Diagrams" extension
- **Firefox**: "Markdown Viewer" with Mermaid support

## Recommended: Use Option 1 (VS Code Extension)
This is the easiest way if you're already using Cursor/VS Code!


