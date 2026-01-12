"""Smart chunking service for code and documentation files.

Provides hybrid chunking strategies:
- AST-based chunking for code files (functions, classes, methods)
- Section-based chunking for documentation (headers, paragraphs)
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class ChunkType(str, Enum):
    """Types of content chunks."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    CODE_BLOCK = "code_block"
    IMPORT = "import"


class Language(str, Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SCALA = "scala"
    SHELL = "shell"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    YAML = "yaml"
    JSON = "json"
    TOML = "toml"
    XML = "xml"
    MARKDOWN = "markdown"
    PLAINTEXT = "plaintext"
    UNKNOWN = "unknown"


# File extension to language mapping
EXTENSION_TO_LANGUAGE: Dict[str, Language] = {
    # Python
    ".py": Language.PYTHON,
    ".pyw": Language.PYTHON,
    ".pyi": Language.PYTHON,
    # JavaScript
    ".js": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".cjs": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    # TypeScript
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".mts": Language.TYPESCRIPT,
    ".cts": Language.TYPESCRIPT,
    # Go
    ".go": Language.GO,
    # Rust
    ".rs": Language.RUST,
    # Java
    ".java": Language.JAVA,
    # C/C++
    ".c": Language.C,
    ".h": Language.C,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".cxx": Language.CPP,
    ".hpp": Language.CPP,
    ".hxx": Language.CPP,
    # C#
    ".cs": Language.CSHARP,
    # Ruby
    ".rb": Language.RUBY,
    ".rake": Language.RUBY,
    # PHP
    ".php": Language.PHP,
    # Swift
    ".swift": Language.SWIFT,
    # Kotlin
    ".kt": Language.KOTLIN,
    ".kts": Language.KOTLIN,
    # Scala
    ".scala": Language.SCALA,
    # Shell
    ".sh": Language.SHELL,
    ".bash": Language.SHELL,
    ".zsh": Language.SHELL,
    # SQL
    ".sql": Language.SQL,
    # Web
    ".html": Language.HTML,
    ".htm": Language.HTML,
    ".css": Language.CSS,
    ".scss": Language.CSS,
    ".sass": Language.CSS,
    ".less": Language.CSS,
    # Data/Config
    ".yaml": Language.YAML,
    ".yml": Language.YAML,
    ".json": Language.JSON,
    ".toml": Language.TOML,
    ".xml": Language.XML,
    # Documentation
    ".md": Language.MARKDOWN,
    ".markdown": Language.MARKDOWN,
    ".rst": Language.PLAINTEXT,
    ".txt": Language.PLAINTEXT,
}


@dataclass
class Chunk:
    """Represents a content chunk with metadata."""

    content: str
    chunk_type: ChunkType
    index: int
    language: Language = Language.UNKNOWN
    name: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    parent_name: Optional[str] = None
    docstring: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    heading: Optional[str] = None
    heading_level: int = 0
    parent_heading: Optional[str] = None
    has_code_blocks: bool = False
    code_languages: List[str] = field(default_factory=list)

    def to_metadata(self) -> Dict[str, Any]:
        """Convert chunk to metadata dictionary for vector storage."""
        metadata = {
            "chunk_type": self.chunk_type.value,
            "chunk_index": self.index,
            "language": self.language.value,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }

        if self.name:
            metadata["name"] = self.name
        if self.parent_name:
            metadata["parent_name"] = self.parent_name
        if self.docstring:
            metadata["docstring"] = self.docstring[:500]  # Truncate
        if self.imports:
            metadata["imports"] = ",".join(self.imports[:20])
        if self.dependencies:
            metadata["dependencies"] = ",".join(self.dependencies[:20])
        if self.exports:
            metadata["exports"] = ",".join(self.exports[:20])
        if self.heading:
            metadata["heading"] = self.heading
        if self.heading_level:
            metadata["heading_level"] = self.heading_level
        if self.parent_heading:
            metadata["parent_heading"] = self.parent_heading
        if self.has_code_blocks:
            metadata["has_code_blocks"] = True
        if self.code_languages:
            metadata["code_languages"] = ",".join(self.code_languages)

        return metadata


class ChunkingService:
    """Service for intelligent content chunking."""

    def __init__(
        self,
        chunk_size_code: int = None,
        chunk_size_docs: int = None,
        chunk_overlap: int = None,
        max_chunks_per_file: int = None,
    ):
        self.chunk_size_code = chunk_size_code or settings.chunk_size_code
        self.chunk_size_docs = chunk_size_docs or settings.chunk_size_docs
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.max_chunks_per_file = max_chunks_per_file or settings.max_chunks_per_file

        # Tree-sitter parsers (lazy loaded)
        self._parsers: Dict[Language, Any] = {}
        self._tree_sitter_available = False
        self._check_tree_sitter()

    def _check_tree_sitter(self):
        """Check if tree-sitter is available."""
        try:
            import tree_sitter  # noqa: F401

            self._tree_sitter_available = True
        except ImportError:
            logger.warning(
                "tree_sitter_not_available",
                message="Falling back to regex-based parsing",
            )
            self._tree_sitter_available = False

    def detect_language(self, file_name: str, content: str = None) -> Language:
        """Detect the programming language from file name and content."""
        # Check file extension
        for ext, lang in EXTENSION_TO_LANGUAGE.items():
            if file_name.lower().endswith(ext):
                return lang

        # Content-based detection for ambiguous cases
        if content:
            content_lower = content[:2000].lower()

            # Shebang detection
            if content.startswith("#!"):
                first_line = content.split("\n")[0].lower()
                if "python" in first_line:
                    return Language.PYTHON
                if "node" in first_line or "deno" in first_line:
                    return Language.JAVASCRIPT
                if "bash" in first_line or "sh" in first_line:
                    return Language.SHELL
                if "ruby" in first_line:
                    return Language.RUBY

            # Keyword detection
            if "def " in content_lower and "import " in content_lower:
                return Language.PYTHON
            if "function " in content_lower or "const " in content_lower:
                if "interface " in content_lower or ": " in content_lower:
                    return Language.TYPESCRIPT
                return Language.JAVASCRIPT
            if "package " in content_lower and "func " in content_lower:
                return Language.GO
            if "fn " in content_lower and "let " in content_lower:
                return Language.RUST

        return Language.UNKNOWN

    def is_code_file(self, language: Language) -> bool:
        """Check if the language represents a code file."""
        non_code_languages = {
            Language.MARKDOWN,
            Language.PLAINTEXT,
            Language.YAML,
            Language.JSON,
            Language.TOML,
            Language.XML,
            Language.HTML,
            Language.CSS,
            Language.UNKNOWN,
        }
        return language not in non_code_languages

    def chunk_content(
        self,
        content: str,
        file_name: str,
        mime_type: str = None,
    ) -> List[Chunk]:
        """Chunk content based on file type and language.

        Args:
            content: The file content to chunk
            file_name: Name of the file (used for language detection)
            mime_type: Optional MIME type

        Returns:
            List of Chunk objects
        """
        language = self.detect_language(file_name, content)

        # Route to appropriate chunker
        if language == Language.MARKDOWN:
            chunks = self._chunk_markdown(content, language)
        elif self.is_code_file(language):
            chunks = self._chunk_code(content, language)
        else:
            # Generic text chunking for config files, etc.
            chunks = self._chunk_text(content, language)

        # Limit number of chunks
        if len(chunks) > self.max_chunks_per_file:
            logger.info(
                "chunks_truncated",
                file_name=file_name,
                original_count=len(chunks),
                max_count=self.max_chunks_per_file,
            )
            chunks = chunks[: self.max_chunks_per_file]

        return chunks

    def _chunk_code(self, content: str, language: Language) -> List[Chunk]:
        """Chunk code using AST-based or regex-based parsing."""
        if self._tree_sitter_available:
            chunks = self._chunk_code_ast(content, language)
            if chunks:
                return chunks

        # Fall back to regex-based parsing
        return self._chunk_code_regex(content, language)

    def _chunk_code_ast(self, content: str, language: Language) -> List[Chunk]:
        """Chunk code using tree-sitter AST parsing."""
        try:
            parser = self._get_parser(language)
            if not parser:
                return []

            tree = parser.parse(bytes(content, "utf-8"))
            chunks = []
            chunk_index = 0

            # Extract imports first
            imports = self._extract_imports_ast(tree.root_node, language, content)

            # Walk the AST and extract semantic units
            for node in self._iter_semantic_nodes(tree.root_node, language):
                chunk_content, chunk_type, name, docstring = self._extract_node_content(
                    node, language, content
                )

                if chunk_content and len(chunk_content.strip()) > 50:
                    chunks.append(
                        Chunk(
                            content=chunk_content,
                            chunk_type=chunk_type,
                            index=chunk_index,
                            language=language,
                            name=name,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            docstring=docstring,
                            imports=imports,
                        )
                    )
                    chunk_index += 1

            # If no semantic chunks found, fall back to fixed chunking
            if not chunks:
                return self._chunk_code_fixed(content, language, imports)

            return chunks

        except Exception as e:
            logger.warning(
                "ast_parsing_failed",
                language=language.value,
                error=str(e),
            )
            return []

    def _get_parser(self, language: Language) -> Optional[Any]:
        """Get or create a tree-sitter parser for the language."""
        if language in self._parsers:
            return self._parsers[language]

        try:
            import tree_sitter

            # Language module mapping
            language_modules = {
                Language.PYTHON: "tree_sitter_python",
                Language.JAVASCRIPT: "tree_sitter_javascript",
                Language.TYPESCRIPT: "tree_sitter_typescript",
                Language.GO: "tree_sitter_go",
                Language.RUST: "tree_sitter_rust",
            }

            if language not in language_modules:
                return None

            module_name = language_modules[language]

            # Try to import the language module
            try:
                module = __import__(module_name)
                # tree-sitter 0.23+ API
                ts_language = module.language()
                parser = tree_sitter.Parser(ts_language)
                self._parsers[language] = parser
                return parser
            except ImportError:
                logger.debug(
                    "tree_sitter_language_not_installed",
                    language=language.value,
                    module=module_name,
                )
                return None
            except TypeError:
                # Fallback for older tree-sitter API
                try:
                    from tree_sitter import Language as TSLanguage
                    ts_language = TSLanguage(module.language())
                    parser = tree_sitter.Parser(ts_language)
                    self._parsers[language] = parser
                    return parser
                except Exception:
                    return None

        except Exception as e:
            logger.warning(
                "tree_sitter_parser_error",
                language=language.value,
                error=str(e),
            )
            return None

    def _iter_semantic_nodes(self, node: Any, language: Language):
        """Iterate over semantic nodes (functions, classes) in the AST."""
        # Node types to extract by language
        semantic_types = {
            Language.PYTHON: {
                "function_definition",
                "class_definition",
                "async_function_definition",
            },
            Language.JAVASCRIPT: {
                "function_declaration",
                "class_declaration",
                "method_definition",
                "arrow_function",
                "function_expression",
            },
            Language.TYPESCRIPT: {
                "function_declaration",
                "class_declaration",
                "method_definition",
                "interface_declaration",
                "type_alias_declaration",
            },
            Language.GO: {
                "function_declaration",
                "method_declaration",
                "type_declaration",
            },
            Language.RUST: {
                "function_item",
                "impl_item",
                "struct_item",
                "enum_item",
                "trait_item",
            },
        }

        target_types = semantic_types.get(language, set())

        def traverse(n):
            if n.type in target_types:
                yield n
            else:
                for child in n.children:
                    yield from traverse(child)

        yield from traverse(node)

    def _extract_node_content(
        self, node: Any, language: Language, content: str
    ) -> Tuple[str, ChunkType, Optional[str], Optional[str]]:
        """Extract content and metadata from an AST node."""
        # Get the raw content
        start_byte = node.start_byte
        end_byte = node.end_byte
        node_content = content[start_byte:end_byte]

        # Determine chunk type
        chunk_type = ChunkType.FUNCTION
        if "class" in node.type:
            chunk_type = ChunkType.CLASS
        elif "method" in node.type:
            chunk_type = ChunkType.METHOD
        elif "interface" in node.type or "type" in node.type:
            chunk_type = ChunkType.CLASS

        # Extract name
        name = None
        for child in node.children:
            if child.type in {"identifier", "name", "property_identifier"}:
                name = content[child.start_byte : child.end_byte]
                break

        # Extract docstring (for Python)
        docstring = None
        if language == Language.PYTHON:
            docstring = self._extract_python_docstring(node, content)

        return node_content, chunk_type, name, docstring

    def _extract_python_docstring(self, node: Any, content: str) -> Optional[str]:
        """Extract docstring from a Python function/class node."""
        for child in node.children:
            if child.type == "block":
                for block_child in child.children:
                    if block_child.type == "expression_statement":
                        for expr_child in block_child.children:
                            if expr_child.type == "string":
                                doc = content[
                                    expr_child.start_byte : expr_child.end_byte
                                ]
                                # Remove quotes
                                doc = doc.strip("\"'")
                                return doc[:500]  # Truncate
        return None

    def _extract_imports_ast(
        self, root: Any, language: Language, content: str
    ) -> List[str]:
        """Extract import statements from AST."""
        imports = []

        import_types = {
            Language.PYTHON: {"import_statement", "import_from_statement"},
            Language.JAVASCRIPT: {"import_statement"},
            Language.TYPESCRIPT: {"import_statement"},
            Language.GO: {"import_declaration"},
            Language.RUST: {"use_declaration"},
        }

        target_types = import_types.get(language, set())

        def traverse(node):
            if node.type in target_types:
                import_text = content[node.start_byte : node.end_byte]
                # Extract module name
                if language == Language.PYTHON:
                    match = re.search(r"(?:from\s+(\S+)|import\s+(\S+))", import_text)
                    if match:
                        imports.append(match.group(1) or match.group(2))
                else:
                    imports.append(import_text[:100])  # Truncate
            for child in node.children:
                traverse(child)

        traverse(root)
        return imports[:20]  # Limit

    def _chunk_code_regex(self, content: str, language: Language) -> List[Chunk]:
        """Chunk code using regex patterns (fallback)."""
        chunks = []
        chunk_index = 0

        # Language-specific patterns
        patterns = {
            Language.PYTHON: [
                (
                    r"^(class\s+\w+.*?:.*?)(?=\nclass\s|\ndef\s|\nasync\s+def\s|\Z)",
                    ChunkType.CLASS,
                ),
                (
                    r"^((?:async\s+)?def\s+\w+.*?:.*?)(?=\ndef\s|\nasync\s+def\s|\nclass\s|\Z)",
                    ChunkType.FUNCTION,
                ),
            ],
            Language.JAVASCRIPT: [
                (r"(class\s+\w+.*?\{.*?\n\})", ChunkType.CLASS),
                (
                    r"((?:async\s+)?function\s+\w+.*?\{.*?\n\})",
                    ChunkType.FUNCTION,
                ),
                (
                    r"(const\s+\w+\s*=\s*(?:async\s+)?\(.*?\)\s*=>.*?(?:;|\n\}))",
                    ChunkType.FUNCTION,
                ),
            ],
            Language.TYPESCRIPT: [
                (r"(interface\s+\w+.*?\{.*?\n\})", ChunkType.CLASS),
                (r"(class\s+\w+.*?\{.*?\n\})", ChunkType.CLASS),
                (
                    r"((?:async\s+)?function\s+\w+.*?\{.*?\n\})",
                    ChunkType.FUNCTION,
                ),
            ],
            Language.GO: [
                (r"(func\s+\w+.*?\{.*?\n\})", ChunkType.FUNCTION),
                (r"(func\s+\(\w+\s+\*?\w+\)\s+\w+.*?\{.*?\n\})", ChunkType.METHOD),
                (r"(type\s+\w+\s+struct\s*\{.*?\n\})", ChunkType.CLASS),
            ],
            Language.RUST: [
                (r"(fn\s+\w+.*?\{.*?\n\})", ChunkType.FUNCTION),
                (r"(impl\s+.*?\{.*?\n\})", ChunkType.CLASS),
                (r"(struct\s+\w+\s*\{.*?\n\})", ChunkType.CLASS),
            ],
        }

        # Extract imports first
        imports = self._extract_imports_regex(content, language)

        lang_patterns = patterns.get(
            language,
            [(r"((?:function|def|fn|func)\s+\w+.*?\{.*?\})", ChunkType.FUNCTION)],
        )

        for pattern, chunk_type in lang_patterns:
            try:
                for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                    chunk_content = match.group(1)
                    if len(chunk_content.strip()) < 50:
                        continue

                    # Calculate line numbers
                    start_pos = match.start()
                    line_start = content[:start_pos].count("\n") + 1
                    line_end = line_start + chunk_content.count("\n")

                    # Extract name
                    name_match = re.search(
                        r"(?:class|def|function|fn|func|interface|type|const)\s+(\w+)",
                        chunk_content,
                    )
                    name = name_match.group(1) if name_match else None

                    chunks.append(
                        Chunk(
                            content=chunk_content,
                            chunk_type=chunk_type,
                            index=chunk_index,
                            language=language,
                            name=name,
                            line_start=line_start,
                            line_end=line_end,
                            imports=imports,
                        )
                    )
                    chunk_index += 1

            except re.error as e:
                logger.warning("regex_pattern_error", pattern=pattern, error=str(e))

        # If no semantic chunks found, use fixed chunking
        if not chunks:
            return self._chunk_code_fixed(content, language, imports)

        return chunks

    def _extract_imports_regex(self, content: str, language: Language) -> List[str]:
        """Extract imports using regex."""
        imports = []

        patterns = {
            Language.PYTHON: r"(?:from\s+(\S+)\s+import|import\s+(\S+))",
            Language.JAVASCRIPT: r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
            Language.TYPESCRIPT: r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
            Language.GO: r"import\s+(?:\(\s*)?([\w\"/\.]+)",
            Language.RUST: r"use\s+([\w:]+)",
        }

        pattern = patterns.get(language)
        if pattern:
            for match in re.finditer(pattern, content[:5000]):  # Only scan start
                import_name = match.group(1) or (
                    match.group(2) if match.lastindex > 1 else None
                )
                if import_name:
                    imports.append(import_name)

        return imports[:20]

    def _chunk_code_fixed(
        self, content: str, language: Language, imports: List[str]
    ) -> List[Chunk]:
        """Chunk code with fixed-size chunks with overlap."""
        chunks = []

        # Estimate tokens (rough: 4 chars per token)
        chars_per_chunk = self.chunk_size_code * 4
        overlap_chars = self.chunk_overlap * 4

        current_pos = 0
        chunk_index = 0

        while current_pos < len(content):
            end_pos = min(current_pos + chars_per_chunk, len(content))

            # Try to end at a line boundary
            if end_pos < len(content):
                next_newline = content.find("\n", end_pos)
                if next_newline != -1 and next_newline - end_pos < 200:
                    end_pos = next_newline + 1

            chunk_content = content[current_pos:end_pos]

            if len(chunk_content.strip()) > 50:
                line_start = content[:current_pos].count("\n") + 1
                line_end = line_start + chunk_content.count("\n")

                chunks.append(
                    Chunk(
                        content=chunk_content,
                        chunk_type=ChunkType.MODULE,
                        index=chunk_index,
                        language=language,
                        line_start=line_start,
                        line_end=line_end,
                        imports=imports if chunk_index == 0 else [],
                    )
                )
                chunk_index += 1

            current_pos = end_pos - overlap_chars
            if current_pos <= 0 or end_pos >= len(content):
                break

        return chunks

    def _chunk_markdown(self, content: str, language: Language) -> List[Chunk]:
        """Chunk markdown by sections (headers)."""
        chunks = []
        chunk_index = 0

        # Split by headers
        header_pattern = r"^(#{1,6})\s+(.+)$"
        lines = content.split("\n")

        current_section = []
        current_heading = None
        current_level = 0
        parent_headings: Dict[int, str] = {}
        section_start_line = 1

        for i, line in enumerate(lines):
            header_match = re.match(header_pattern, line)

            if header_match:
                # Save previous section
                if current_section:
                    section_content = "\n".join(current_section)
                    if len(section_content.strip()) > 30:
                        # Detect code blocks in section
                        code_blocks = re.findall(
                            r"```(\w*)\n", section_content, re.MULTILINE
                        )
                        code_languages = [
                            lang for lang in code_blocks if lang
                        ]

                        parent_heading = None
                        for level in range(current_level - 1, 0, -1):
                            if level in parent_headings:
                                parent_heading = parent_headings[level]
                                break

                        chunks.append(
                            Chunk(
                                content=section_content,
                                chunk_type=ChunkType.SECTION,
                                index=chunk_index,
                                language=language,
                                line_start=section_start_line,
                                line_end=i,
                                heading=current_heading,
                                heading_level=current_level,
                                parent_heading=parent_heading,
                                has_code_blocks=bool(code_blocks),
                                code_languages=code_languages,
                            )
                        )
                        chunk_index += 1

                # Start new section
                current_level = len(header_match.group(1))
                current_heading = header_match.group(2)
                parent_headings[current_level] = current_heading
                current_section = [line]
                section_start_line = i + 1

            else:
                current_section.append(line)

        # Save last section
        if current_section:
            section_content = "\n".join(current_section)
            if len(section_content.strip()) > 30:
                code_blocks = re.findall(r"```(\w*)\n", section_content, re.MULTILINE)
                code_languages = [lang for lang in code_blocks if lang]

                parent_heading = None
                for level in range(current_level - 1, 0, -1):
                    if level in parent_headings:
                        parent_heading = parent_headings[level]
                        break

                chunks.append(
                    Chunk(
                        content=section_content,
                        chunk_type=ChunkType.SECTION,
                        index=chunk_index,
                        language=language,
                        line_start=section_start_line,
                        line_end=len(lines),
                        heading=current_heading,
                        heading_level=current_level,
                        parent_heading=parent_heading,
                        has_code_blocks=bool(code_blocks),
                        code_languages=code_languages,
                    )
                )

        # If no headers found, use fixed chunking
        if not chunks:
            return self._chunk_text(content, language)

        # Split large sections
        final_chunks = []
        for chunk in chunks:
            if len(chunk.content) > self.chunk_size_docs * 4:
                sub_chunks = self._split_large_section(chunk)
                for i, sub in enumerate(sub_chunks):
                    sub.index = len(final_chunks)
                    final_chunks.append(sub)
            else:
                chunk.index = len(final_chunks)
                final_chunks.append(chunk)

        return final_chunks

    def _split_large_section(self, chunk: Chunk) -> List[Chunk]:
        """Split a large section into smaller chunks with overlap."""
        content = chunk.content
        chars_per_chunk = self.chunk_size_docs * 4
        overlap_chars = self.chunk_overlap * 4

        sub_chunks = []
        current_pos = 0
        sub_index = 0

        while current_pos < len(content):
            end_pos = min(current_pos + chars_per_chunk, len(content))

            # Try to end at a sentence or paragraph boundary
            if end_pos < len(content):
                # Look for paragraph break
                para_break = content.find("\n\n", end_pos - 100, end_pos + 100)
                if para_break != -1:
                    end_pos = para_break + 2
                else:
                    # Look for sentence end
                    for end_char in [". ", ".\n", "! ", "? "]:
                        sent_end = content.rfind(end_char, current_pos, end_pos + 50)
                        if sent_end != -1:
                            end_pos = sent_end + 2
                            break

            sub_content = content[current_pos:end_pos]

            if len(sub_content.strip()) > 30:
                sub_chunks.append(
                    Chunk(
                        content=sub_content,
                        chunk_type=chunk.chunk_type,
                        index=sub_index,
                        language=chunk.language,
                        line_start=chunk.line_start,
                        line_end=chunk.line_end,
                        heading=chunk.heading,
                        heading_level=chunk.heading_level,
                        parent_heading=chunk.parent_heading,
                        has_code_blocks=chunk.has_code_blocks,
                        code_languages=chunk.code_languages,
                    )
                )
                sub_index += 1

            current_pos = end_pos - overlap_chars
            if current_pos <= 0 or end_pos >= len(content):
                break

        return sub_chunks if sub_chunks else [chunk]

    def _chunk_text(self, content: str, language: Language) -> List[Chunk]:
        """Generic text chunking with fixed size and overlap."""
        chunks = []
        chars_per_chunk = self.chunk_size_docs * 4
        overlap_chars = self.chunk_overlap * 4

        current_pos = 0
        chunk_index = 0

        while current_pos < len(content):
            end_pos = min(current_pos + chars_per_chunk, len(content))

            # Try to end at a paragraph or sentence boundary
            if end_pos < len(content):
                para_break = content.find("\n\n", end_pos - 100, end_pos + 100)
                if para_break != -1:
                    end_pos = para_break + 2
                else:
                    for end_char in [". ", ".\n"]:
                        sent_end = content.rfind(end_char, current_pos, end_pos + 50)
                        if sent_end != -1:
                            end_pos = sent_end + 2
                            break

            chunk_content = content[current_pos:end_pos]

            if len(chunk_content.strip()) > 30:
                line_start = content[:current_pos].count("\n") + 1
                line_end = line_start + chunk_content.count("\n")

                chunks.append(
                    Chunk(
                        content=chunk_content,
                        chunk_type=ChunkType.PARAGRAPH,
                        index=chunk_index,
                        language=language,
                        line_start=line_start,
                        line_end=line_end,
                    )
                )
                chunk_index += 1

            current_pos = end_pos - overlap_chars
            if current_pos <= 0 or end_pos >= len(content):
                break

        return chunks


# Global instance
chunking_service = ChunkingService()
