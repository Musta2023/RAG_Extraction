# Contributing to RAG FastAPI

We welcome contributions from the community! Whether you're fixing a bug, improving documentation, or proposing a new feature, your help is appreciated. Please take a moment to review this document to make the contribution process easy and effective for everyone.

## How to Contribute

### Reporting Bugs

- If you find a bug, please first check the [issue tracker](https://github.com/your-repo/rag-fastapi/issues) to see if it has already been reported.
- If not, create a new issue. Be sure to include:
    - A clear and descriptive title.
    - A detailed description of the problem, including the steps to reproduce it.
    - Information about your environment (e.g., operating system, Python version, Docker version).
    - Any relevant logs or error messages.

### Suggesting Enhancements

- If you have an idea for a new feature or an improvement to an existing one, please open an issue to start a discussion.
- This allows us to align on the proposal before you put significant effort into implementation.

### Submitting Pull Requests

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally:
    ```bash
    git clone https://github.com/your-username/rag-fastapi.git
    cd rag-fastapi
    ```
3.  **Create a new branch** for your changes:
    ```bash
    git checkout -b feature/your-feature-name
    ```
    Or for a bug fix:
    ```bash
    git checkout -b fix/bug-description
    ```
4.  **Set up your development environment** as described in the `README.md`.
5.  **Make your changes**. Ensure you follow the project's coding style and conventions.
6.  **Add or update tests** for your changes. We aim for high test coverage.
7.  **Run the tests** to ensure everything is passing:
    ```bash
    pytest
    ```
8.  **Commit your changes** with a clear and descriptive commit message. We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.
    - Example: `feat: Add support for Cohere embedding models`
    - Example: `fix: Correctly handle timeouts during web crawling`
9.  **Push your branch** to your fork on GitHub:
    ```bash
    git push origin feature/your-feature-name
    ```
10. **Open a Pull Request (PR)** from your fork to the `main` branch of the original repository.
    - Provide a clear title and a detailed description of your changes in the PR.
    - Link to any relevant issues.

## Coding Style

- We use **Black** for code formatting and **Ruff** for linting. Please run these tools on your code before committing.
- Strive to write clean, readable, and well-commented code, especially for complex logic.
- Follow the existing code structure and patterns.

## Code of Conduct

By participating in this project, you are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Please be respectful and considerate of others.

Thank you for your contributions!