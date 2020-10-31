from io import open

from setuptools import find_packages, setup


def parse_requirements(filename):
    with open(filename) as file:
        lines = file.read().splitlines()

    return [
        line.strip()
        for line in lines
        if not (
            (line.strip()[0] == "#") or
            (line.strip().startswith('--find-links')) or
            ("git+https" in line)
        )
    ]


def get_dependency_links(filename):
    with open(filename) as file:
        lines = file.read().splitlines()

    return [
        line.strip().split('=')[1]
        for line in lines
        if line.strip().startswith('--find-links')
    ]


dependency_links = get_dependency_links('requirements.txt')
parsed_requirements = parse_requirements('requirements.txt')

setup(
    name="social-tracker",
    version="0.0.1",
    author="Lalit Pagaria",
    author_email="pagaria.lalit@gmail.com",
    description="",
    license="GPL Version 3",
    url="https://github.com/lalitpagaria/SocialTracker",
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    dependency_links=dependency_links,
    install_requires=parsed_requirements,
    python_requires=">=3.8.0",
    tests_require=["pytest"],
)
