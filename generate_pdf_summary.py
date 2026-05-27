from fpdf import FPDF
import os

class PDFSummary(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'AI Test Platform - One Page Summary', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)

    def chapter_body(self, body):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 6, body)
        self.ln(4)

    def add_bullet_point(self, text):
        self.set_font('Helvetica', '', 10)
        self.cell(5, 6, chr(149), 0)  # Bullet point
        self.cell(0, 6, f' {text}', 0, 1)
        self.ln(1)

def create_ai_test_platform_summary():
    pdf = PDFSummary()
    pdf.add_page()
    
    # What it is
    pdf.chapter_title('What it is:')
    pdf.chapter_body('AI Test Platform is an enterprise-grade automated testing platform that combines deterministic automation with AI enhancement capabilities. It aims to provide a complete platform for AI-driven testing in enterprise R&D scenarios.')
    
    # Who it's for
    pdf.chapter_title('Who it\'s for:')
    pdf.chapter_body('Primary users are enterprise R&D teams, QA engineers, and development organizations looking to implement comprehensive AI-enhanced testing solutions. It serves teams seeking to automate test generation, execution, and analysis with intelligent insights.')
    
    # What it does
    pdf.chapter_title('What it does:')
    features = [
        "Deterministic automation testing foundation with Playwright, API, and Appium support",
        "AI-powered test point generation from PRDs, prototypes, and OpenAPI specifications",
        "AI-generated test script drafts for Web/API/Mobile platforms",
        "Intelligent failure attribution and root cause analysis",
        "Smart regression recommendation and quality analysis",
        "Evidence collection (traces, screenshots, videos, logs)",
        "Quality metrics and release gatekeeping functionality"
    ]
    
    for feature in features:
        pdf.add_bullet_point(feature)
    
    # How it works
    pdf.chapter_title('How it works:')
    architecture_desc = (
        "The platform follows a layered architecture:\n\n"
        "Input Layer: PRDs, Swagger docs, Git diffs, defect tickets\n"
        "Arrow: -->\n"
        "Test Asset Center: Test case libraries, page objects, API contracts\n"
        "Arrow: -->\n"
        "AI Orchestration Layer: Requirement parsing, test design, script generation, failure analysis\n"
        "Arrow: -->\n"
        "Automation Execution: Web/API/Mobile testing runners\n"
        "Arrow: -->\n"
        "Execution & Scheduling: CI/CD integration, concurrency control\n"
        "Arrow: -->\n"
        "Evidence Collection: Traces, screenshots, videos, logs\n"
        "Arrow: -->\n"
        "Quality Analysis: Flaky analysis, failure clustering, trend analysis\n"
        "Arrow: -->\n"
        "Release Governance: PR gates, smoke gates, regression gates\n\n"
        "Technology Stack: FastAPI backend, PostgreSQL/SQLite, Redis, Docker, ELK stack for observability."
    )
    pdf.chapter_body(architecture_desc)
    
    # How to run
    pdf.chapter_title('How to run:')
    run_steps = (
        "1. Initialize Python environment: make install-dev\n"
        "2. Install pre-commit hooks (optional): make install-hooks\n"
        "3. Start the platform: docker-compose up --build\n"
        "4. Run tests: make test\n"
        "5. Alternative direct execution:\n"
        "   - Navigate to apps/web-ui-service/\n"
        "   - Run: python -m uvicorn app.main:app --reload"
    )
    pdf.chapter_body(run_steps)
    
    # Save the PDF
    filename = "ai_test_platform_summary.pdf"
    pdf.output(filename)
    return filename

if __name__ == "__main__":
    filename = create_ai_test_platform_summary()
    print(f"PDF summary generated: {filename}")
