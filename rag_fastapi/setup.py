from setuptools import setup, find_packages

setup(
    name='rag_fastapi',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        # See requirements.txt for full list
        # This setup.py is mainly for packaging, not direct installation of all deps
        # For development, use requirements.txt
    ],
    entry_points={
        'console_scripts': [
            'rag-api=app.main:app', # Example, if you want a CLI entrypoint
        ],
    },
    author='Your Name',
    author_email='your.email@example.com',
    description='A FastAPI project implementing a Web-based Retrieval-Augmented Generation (RAG) pipeline.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/your-repo/rag_fastapi',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
)