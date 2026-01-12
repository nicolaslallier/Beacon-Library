"""Metadata extraction service for code and documentation files.

Provides rich metadata extraction for:
- Programming language detection
- Code structure analysis (imports, exports, dependencies)
- Document structure analysis (sections, headings)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from app.services.chunking import (
    EXTENSION_TO_LANGUAGE,
    Language,
)

logger = structlog.get_logger(__name__)


@dataclass
class CodeMetadata:
    """Metadata extracted from code files."""

    language: Language
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)
    types: List[str] = field(default_factory=list)
    constants: List[str] = field(default_factory=list)
    has_tests: bool = False
    has_types: bool = False
    frameworks: List[str] = field(default_factory=list)
    line_count: int = 0
    comment_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "language": self.language.value,
            "imports": ",".join(self.imports[:30]),
            "exports": ",".join(self.exports[:30]),
            "dependencies": ",".join(self.dependencies[:30]),
            "functions": ",".join(self.functions[:30]),
            "classes": ",".join(self.classes[:20]),
            "interfaces": ",".join(self.interfaces[:20]),
            "types": ",".join(self.types[:20]),
            "constants": ",".join(self.constants[:20]),
            "has_tests": self.has_tests,
            "has_types": self.has_types,
            "frameworks": ",".join(self.frameworks[:10]),
            "line_count": self.line_count,
            "comment_ratio": round(self.comment_ratio, 2),
        }


@dataclass
class DocumentMetadata:
    """Metadata extracted from documentation files."""

    doc_type: str  # markdown, rst, txt, etc.
    title: Optional[str] = None
    headings: List[str] = field(default_factory=list)
    heading_structure: List[Dict[str, Any]] = field(default_factory=list)
    has_code_blocks: bool = False
    code_languages: List[str] = field(default_factory=list)
    has_tables: bool = False
    has_images: bool = False
    has_links: bool = False
    internal_links: List[str] = field(default_factory=list)
    external_links: List[str] = field(default_factory=list)
    word_count: int = 0
    section_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "doc_type": self.doc_type,
            "title": self.title or "",
            "headings": ",".join(self.headings[:20]),
            "has_code_blocks": self.has_code_blocks,
            "code_languages": ",".join(self.code_languages[:10]),
            "has_tables": self.has_tables,
            "has_images": self.has_images,
            "has_links": self.has_links,
            "word_count": self.word_count,
            "section_count": self.section_count,
        }


class MetadataExtractionService:
    """Service for extracting rich metadata from files."""

    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        "react": [r"import.*from\s+['\"]react['\"]", r"React\.", r"useState", r"useEffect"],
        "vue": [r"import.*from\s+['\"]vue['\"]", r"defineComponent", r"<template>"],
        "angular": [r"@Component", r"@Injectable", r"@NgModule"],
        "fastapi": [r"from fastapi", r"@app\.(get|post|put|delete)", r"FastAPI"],
        "django": [r"from django", r"models\.Model", r"views\."],
        "flask": [r"from flask", r"Flask\(", r"@app\.route"],
        "express": [r"require\(['\"]express['\"]", r"express\(\)", r"app\.(get|post)"],
        "nestjs": [r"@Controller", r"@Injectable", r"@Module"],
        "spring": [r"@SpringBootApplication", r"@RestController", r"@Service"],
        "pytest": [r"import pytest", r"@pytest\.", r"def test_"],
        "jest": [r"describe\(", r"it\(", r"expect\(", r"test\("],
        "unittest": [r"import unittest", r"TestCase", r"self\.assert"],
        "sqlalchemy": [r"from sqlalchemy", r"Column\(", r"relationship\("],
        "prisma": [r"@prisma/client", r"PrismaClient"],
        "tensorflow": [r"import tensorflow", r"tf\."],
        "pytorch": [r"import torch", r"torch\."],
        "pandas": [r"import pandas", r"pd\.DataFrame"],
        "numpy": [r"import numpy", r"np\."],
    }

    # Test file patterns
    TEST_PATTERNS = [
        r"test_\w+\.py$",
        r"\w+_test\.py$",
        r"\.test\.(js|ts|tsx)$",
        r"\.spec\.(js|ts|tsx)$",
        r"test\.(js|ts|tsx)$",
        r"spec\.(js|ts|tsx)$",
    ]

    def __init__(self):
        self._tree_sitter_available = False
        self._check_tree_sitter()

    def _check_tree_sitter(self):
        """Check if tree-sitter is available."""
        try:
            import tree_sitter  # noqa: F401
            self._tree_sitter_available = True
        except ImportError:
            self._tree_sitter_available = False

    def detect_language(self, file_name: str, content: str = None) -> Language:
        """Detect programming language from file name and content."""
        # Check file extension first
        for ext, lang in EXTENSION_TO_LANGUAGE.items():
            if file_name.lower().endswith(ext):
                return lang

        # Content-based detection
        if content:
            return self._detect_language_from_content(content)

        return Language.UNKNOWN

    def _detect_language_from_content(self, content: str) -> Language:
        """Detect language from content analysis."""
        content_sample = content[:3000].lower()

        # Shebang detection
        if content.startswith("#!"):
            first_line = content.split("\n")[0].lower()
            if "python" in first_line:
                return Language.PYTHON
            if "node" in first_line:
                return Language.JAVASCRIPT
            if "bash" in first_line or "/sh" in first_line:
                return Language.SHELL
            if "ruby" in first_line:
                return Language.RUBY
            if "perl" in first_line:
                return Language.UNKNOWN

        # Keyword-based detection
        language_scores: Dict[Language, int] = {}

        python_keywords = ["def ", "import ", "from ", "class ", "if __name__"]
        js_keywords = ["function ", "const ", "let ", "var ", "=>", "require("]
        ts_keywords = ["interface ", "type ", ": string", ": number", ": boolean"]
        go_keywords = ["package ", "func ", "import (", "type ", "struct {"]
        rust_keywords = ["fn ", "let ", "mut ", "impl ", "struct ", "enum "]
        java_keywords = ["public class", "private ", "void ", "String ", "import java"]

        for kw in python_keywords:
            if kw in content_sample:
                language_scores[Language.PYTHON] = language_scores.get(Language.PYTHON, 0) + 1

        for kw in js_keywords:
            if kw in content_sample:
                language_scores[Language.JAVASCRIPT] = language_scores.get(Language.JAVASCRIPT, 0) + 1

        for kw in ts_keywords:
            if kw in content_sample:
                language_scores[Language.TYPESCRIPT] = language_scores.get(Language.TYPESCRIPT, 0) + 1

        for kw in go_keywords:
            if kw in content_sample:
                language_scores[Language.GO] = language_scores.get(Language.GO, 0) + 1

        for kw in rust_keywords:
            if kw in content_sample:
                language_scores[Language.RUST] = language_scores.get(Language.RUST, 0) + 1

        for kw in java_keywords:
            if kw in content_sample:
                language_scores[Language.JAVA] = language_scores.get(Language.JAVA, 0) + 1

        if language_scores:
            return max(language_scores, key=language_scores.get)

        return Language.UNKNOWN

    def extract_code_metadata(
        self, content: str, file_name: str, language: Language = None
    ) -> CodeMetadata:
        """Extract metadata from code content."""
        if language is None:
            language = self.detect_language(file_name, content)

        metadata = CodeMetadata(language=language)
        metadata.line_count = content.count("\n") + 1

        # Extract imports
        metadata.imports = self._extract_imports(content, language)

        # Extract exports
        metadata.exports = self._extract_exports(content, language)

        # Extract function/class names
        metadata.functions = self._extract_functions(content, language)
        metadata.classes = self._extract_classes(content, language)
        metadata.interfaces = self._extract_interfaces(content, language)
        metadata.types = self._extract_types(content, language)
        metadata.constants = self._extract_constants(content, language)

        # Calculate dependencies (imported modules used in code)
        metadata.dependencies = self._extract_dependencies(
            content, metadata.imports, language
        )

        # Detect frameworks
        metadata.frameworks = self._detect_frameworks(content)

        # Check for tests
        metadata.has_tests = self._is_test_file(file_name, content)

        # Check for type annotations
        metadata.has_types = self._has_type_annotations(content, language)

        # Calculate comment ratio
        metadata.comment_ratio = self._calculate_comment_ratio(content, language)

        return metadata

    def _extract_imports(self, content: str, language: Language) -> List[str]:
        """Extract import statements."""
        imports = []

        patterns = {
            Language.PYTHON: [
                r"^from\s+([\w.]+)\s+import",
                r"^import\s+([\w.]+)",
            ],
            Language.JAVASCRIPT: [
                r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
                r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            ],
            Language.TYPESCRIPT: [
                r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
                r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            ],
            Language.GO: [
                r"import\s+['\"]([^'\"]+)['\"]",
                r"import\s+\w+\s+['\"]([^'\"]+)['\"]",
            ],
            Language.RUST: [
                r"use\s+([\w:]+)",
                r"extern\s+crate\s+(\w+)",
            ],
            Language.JAVA: [
                r"import\s+([\w.]+)",
            ],
        }

        lang_patterns = patterns.get(language, [])

        for pattern in lang_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                import_name = match.group(1)
                if import_name and import_name not in imports:
                    imports.append(import_name)

        return imports[:50]  # Limit

    def _extract_exports(self, content: str, language: Language) -> List[str]:
        """Extract exported symbols."""
        exports = []

        if language in {Language.JAVASCRIPT, Language.TYPESCRIPT}:
            # Named exports
            for match in re.finditer(r"export\s+(?:const|let|var|function|class|interface|type)\s+(\w+)", content):
                exports.append(match.group(1))
            # Default exports
            for match in re.finditer(r"export\s+default\s+(?:function\s+)?(\w+)", content):
                exports.append(match.group(1))
            # Export list
            for match in re.finditer(r"export\s*\{([^}]+)\}", content):
                for name in re.findall(r"(\w+)", match.group(1)):
                    if name not in {"as", "from"}:
                        exports.append(name)

        elif language == Language.PYTHON:
            # __all__ definition
            all_match = re.search(r"__all__\s*=\s*\[([^\]]+)\]", content)
            if all_match:
                for name in re.findall(r"['\"](\w+)['\"]", all_match.group(1)):
                    exports.append(name)
            else:
                # Public functions/classes (not starting with _)
                for match in re.finditer(r"^(?:def|class)\s+([a-zA-Z]\w*)", content, re.MULTILINE):
                    exports.append(match.group(1))

        elif language == Language.GO:
            # Exported symbols start with uppercase
            for match in re.finditer(r"^(?:func|type|var|const)\s+([A-Z]\w*)", content, re.MULTILINE):
                exports.append(match.group(1))

        elif language == Language.RUST:
            # pub items
            for match in re.finditer(r"pub\s+(?:fn|struct|enum|trait|type|const)\s+(\w+)", content):
                exports.append(match.group(1))

        return list(set(exports))[:30]

    def _extract_functions(self, content: str, language: Language) -> List[str]:
        """Extract function names."""
        functions = []

        patterns = {
            Language.PYTHON: r"^(?:async\s+)?def\s+(\w+)",
            Language.JAVASCRIPT: r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))",
            Language.TYPESCRIPT: r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))",
            Language.GO: r"^func\s+(?:\([^)]+\)\s+)?(\w+)",
            Language.RUST: r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)",
            Language.JAVA: r"(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+\s*)?\{",
        }

        pattern = patterns.get(language)
        if pattern:
            for match in re.finditer(pattern, content, re.MULTILINE):
                name = match.group(1) or (match.group(2) if match.lastindex > 1 else None)
                if name and name not in functions:
                    functions.append(name)

        return functions[:50]

    def _extract_classes(self, content: str, language: Language) -> List[str]:
        """Extract class names."""
        classes = []

        patterns = {
            Language.PYTHON: r"^class\s+(\w+)",
            Language.JAVASCRIPT: r"class\s+(\w+)",
            Language.TYPESCRIPT: r"class\s+(\w+)",
            Language.GO: r"type\s+(\w+)\s+struct",
            Language.RUST: r"(?:pub\s+)?struct\s+(\w+)",
            Language.JAVA: r"(?:public\s+)?class\s+(\w+)",
        }

        pattern = patterns.get(language)
        if pattern:
            for match in re.finditer(pattern, content, re.MULTILINE):
                if match.group(1) not in classes:
                    classes.append(match.group(1))

        return classes[:30]

    def _extract_interfaces(self, content: str, language: Language) -> List[str]:
        """Extract interface/trait names."""
        interfaces = []

        if language == Language.TYPESCRIPT:
            for match in re.finditer(r"interface\s+(\w+)", content):
                interfaces.append(match.group(1))

        elif language == Language.GO:
            for match in re.finditer(r"type\s+(\w+)\s+interface", content):
                interfaces.append(match.group(1))

        elif language == Language.RUST:
            for match in re.finditer(r"(?:pub\s+)?trait\s+(\w+)", content):
                interfaces.append(match.group(1))

        elif language == Language.JAVA:
            for match in re.finditer(r"interface\s+(\w+)", content):
                interfaces.append(match.group(1))

        return interfaces[:20]

    def _extract_types(self, content: str, language: Language) -> List[str]:
        """Extract type aliases."""
        types = []

        if language == Language.TYPESCRIPT:
            for match in re.finditer(r"type\s+(\w+)\s*=", content):
                types.append(match.group(1))

        elif language == Language.GO:
            for match in re.finditer(r"type\s+(\w+)\s+(?!struct|interface)", content):
                types.append(match.group(1))

        elif language == Language.RUST:
            for match in re.finditer(r"type\s+(\w+)\s*=", content):
                types.append(match.group(1))

        return types[:20]

    def _extract_constants(self, content: str, language: Language) -> List[str]:
        """Extract constant definitions."""
        constants = []

        if language == Language.PYTHON:
            # UPPER_CASE variables at module level
            for match in re.finditer(r"^([A-Z][A-Z0-9_]+)\s*=", content, re.MULTILINE):
                constants.append(match.group(1))

        elif language in {Language.JAVASCRIPT, Language.TYPESCRIPT}:
            for match in re.finditer(r"const\s+([A-Z][A-Z0-9_]+)\s*=", content):
                constants.append(match.group(1))

        elif language == Language.GO:
            for match in re.finditer(r"const\s+(\w+)\s*=", content):
                constants.append(match.group(1))

        elif language == Language.RUST:
            for match in re.finditer(r"const\s+([A-Z][A-Z0-9_]+)\s*:", content):
                constants.append(match.group(1))

        return constants[:20]

    def _extract_dependencies(
        self, content: str, imports: List[str], language: Language
    ) -> List[str]:
        """Extract which imports are actually used in code."""
        dependencies = []

        for imp in imports:
            # Get the base module name
            if language == Language.PYTHON:
                base_name = imp.split(".")[0]
            elif language in {Language.JAVASCRIPT, Language.TYPESCRIPT}:
                base_name = imp.split("/")[0].lstrip("@")
            else:
                base_name = imp.split("/")[-1].split(".")[-1]

            # Check if it's used in the code (simple heuristic)
            if base_name and re.search(rf"\b{re.escape(base_name)}\b", content):
                dependencies.append(imp)

        return dependencies[:30]

    def _detect_frameworks(self, content: str) -> List[str]:
        """Detect frameworks/libraries used in the code."""
        detected = []

        for framework, patterns in self.FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    detected.append(framework)
                    break

        return detected

    def _is_test_file(self, file_name: str, content: str) -> bool:
        """Check if this is a test file."""
        # Check file name
        for pattern in self.TEST_PATTERNS:
            if re.search(pattern, file_name, re.IGNORECASE):
                return True

        # Check content for test patterns
        test_indicators = [
            r"def test_",
            r"@pytest",
            r"describe\(",
            r"it\(",
            r"test\(",
            r"@Test",
            r"TestCase",
            r"unittest",
        ]

        for indicator in test_indicators:
            if re.search(indicator, content):
                return True

        return False

    def _has_type_annotations(self, content: str, language: Language) -> bool:
        """Check if the code has type annotations."""
        if language == Language.PYTHON:
            # Check for type hints
            return bool(re.search(r":\s*(?:str|int|float|bool|List|Dict|Optional|Any|Tuple)", content))

        elif language == Language.TYPESCRIPT:
            # TypeScript always has types
            return True

        elif language == Language.GO:
            # Go always has types
            return True

        elif language == Language.RUST:
            # Rust always has types
            return True

        elif language == Language.JAVA:
            # Java always has types
            return True

        return False

    def _calculate_comment_ratio(self, content: str, language: Language) -> float:
        """Calculate the ratio of comment lines to total lines."""
        lines = content.split("\n")
        if not lines:
            return 0.0

        comment_lines = 0

        comment_patterns: Dict[Language, tuple] = {
            Language.PYTHON: (r"^\s*#", r'^\s*"""', r"^\s*'''"),
            Language.JAVASCRIPT: (r"^\s*//", r"^\s*/\*"),
            Language.TYPESCRIPT: (r"^\s*//", r"^\s*/\*"),
            Language.GO: (r"^\s*//", r"^\s*/\*"),
            Language.RUST: (r"^\s*//", r"^\s*/\*"),
            Language.JAVA: (r"^\s*//", r"^\s*/\*"),
        }

        patterns = comment_patterns.get(language, (r"^\s*#", r"^\s*//"))

        for line in lines:
            if not line.strip():
                continue

            for pattern in patterns:
                if re.match(pattern, line):
                    comment_lines += 1
                    break

        return comment_lines / len(lines) if lines else 0.0

    def extract_document_metadata(
        self, content: str, file_name: str
    ) -> DocumentMetadata:
        """Extract metadata from documentation content."""
        # Determine document type
        doc_type = "markdown"
        if file_name.endswith(".rst"):
            doc_type = "rst"
        elif file_name.endswith(".txt"):
            doc_type = "text"
        elif file_name.endswith(".html"):
            doc_type = "html"

        metadata = DocumentMetadata(doc_type=doc_type)

        # Extract title (first h1)
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            metadata.title = title_match.group(1).strip()

        # Extract headings
        metadata.headings = []
        metadata.heading_structure = []

        for match in re.finditer(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE):
            level = len(match.group(1))
            heading = match.group(2).strip()
            metadata.headings.append(heading)
            metadata.heading_structure.append({
                "level": level,
                "text": heading,
                "line": content[:match.start()].count("\n") + 1,
            })

        metadata.section_count = len(metadata.headings)

        # Check for code blocks
        code_blocks = re.findall(r"```(\w*)", content)
        metadata.has_code_blocks = bool(code_blocks)
        metadata.code_languages = list(set(lang for lang in code_blocks if lang))

        # Check for tables
        metadata.has_tables = bool(re.search(r"^\|.+\|$", content, re.MULTILINE))

        # Check for images
        metadata.has_images = bool(re.search(r"!\[.*?\]\(.*?\)", content))

        # Extract links
        metadata.has_links = bool(re.search(r"\[.*?\]\(.*?\)", content))

        all_links = re.findall(r"\[.*?\]\((.*?)\)", content)
        for link in all_links:
            if link.startswith("http://") or link.startswith("https://"):
                metadata.external_links.append(link)
            else:
                metadata.internal_links.append(link)

        metadata.external_links = metadata.external_links[:20]
        metadata.internal_links = metadata.internal_links[:20]

        # Word count
        text_content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        text_content = re.sub(r"`[^`]+`", "", text_content)
        words = re.findall(r"\b\w+\b", text_content)
        metadata.word_count = len(words)

        return metadata


# Global instance
metadata_extraction_service = MetadataExtractionService()
