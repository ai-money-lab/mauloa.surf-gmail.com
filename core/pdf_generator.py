"""PDF generation from Markdown templates using WeasyPrint."""

import logging
from pathlib import Path
from typing import Optional

from jinja2 import Template
import markdown

logger = logging.getLogger(__name__)

CSS_TEMPLATE = """
@page {
    size: A4;
    margin: 2cm;
    @bottom-center {
        content: "ROCKEDGE Property Management — Confidential";
        font-size: 8pt;
        color: #888;
    }
    @bottom-right {
        content: counter(page);
        font-size: 8pt;
        color: #888;
    }
}
body {
    font-family: 'Noto Sans JP', 'Hiragino Sans', sans-serif;
    font-size: 11pt;
    line-height: 1.8;
    color: #333;
}
h1 { font-size: 22pt; border-bottom: 2px solid #2c3e50; padding-bottom: 8px; }
h2 { font-size: 16pt; color: #2c3e50; margin-top: 24px; }
h3 { font-size: 13pt; color: #34495e; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
th { background-color: #2c3e50; color: white; }
tr:nth-child(even) { background-color: #f9f9f9; }
.cover { text-align: center; padding-top: 200px; }
.cover h1 { border: none; font-size: 28pt; }
.cover .subtitle { font-size: 14pt; color: #666; margin-top: 20px; }
.cover .meta { margin-top: 60px; color: #888; }
"""


class PDFGenerator:
    """Generate PDF reports from Markdown templates."""

    def __init__(self, template_dir: Optional[str] = None):
        self.template_dir = Path(template_dir or (Path(__file__).parent.parent / "templates"))

    def render_template(self, template_name: str, variables: dict) -> str:
        """Render a Markdown template with Jinja2 variables."""
        template_path = self.template_dir / template_name
        raw = template_path.read_text(encoding="utf-8")
        template = Template(raw)
        return template.render(**variables)

    def markdown_to_html(self, md_text: str) -> str:
        """Convert Markdown to HTML."""
        extensions = ["tables", "toc", "fenced_code", "nl2br"]
        html_body = markdown.markdown(md_text, extensions=extensions)
        return f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><style>{CSS_TEMPLATE}</style></head>
<body>{html_body}</body>
</html>"""

    def generate_pdf(
        self,
        template_name: str,
        variables: dict,
        output_path: str,
    ) -> str:
        """Generate a PDF from a Markdown template.

        Args:
            template_name: Name of the .md template file.
            variables: Template variables to fill in.
            output_path: Where to save the generated PDF.

        Returns:
            Path to the generated PDF.
        """
        try:
            from weasyprint import HTML
        except ImportError:
            logger.error("weasyprint is not installed. Install with: pip install weasyprint")
            raise

        md_content = self.render_template(template_name, variables)
        html_content = self.markdown_to_html(md_content)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        HTML(string=html_content).write_pdf(str(output))
        logger.info("PDF generated: %s", output)
        return str(output)
