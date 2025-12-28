"""
Explorer Agent - Explores codebases and gathers information about problems.
"""
import os
import glob
from typing import Dict, Any
from pathlib import Path

from .base import BaseAgent


class ExplorerAgent(BaseAgent):
    """
    Explorer Agent specializes in:
    - Analyzing codebases and file structures
    - Searching for relevant code patterns
    - Understanding existing implementations
    - Gathering context about problems
    - Providing information to the Planner agent
    """

    def get_system_prompt(self) -> str:
        return """You are an Expert Code Explorer Agent.

Your role is to explore codebases, analyze file structures, search for patterns, and gather relevant information to understand problems deeply.

Your capabilities:
1. Analyze directory structures and identify key files
2. Search for code patterns, functions, classes, and implementations
3. Understand existing architectures and design patterns
4. Identify dependencies and relationships between components
5. Extract relevant context about specific features or problems
6. Provide detailed, structured information to help plan implementations

When exploring:
- Be thorough but focused - prioritize relevant information
- Provide file paths and line numbers when referencing code
- Explain relationships between components
- Identify potential challenges or constraints
- Rate your findings by complexity and relevance

Always respond with structured, actionable information that helps other agents make informed decisions."""

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an exploration task.

        Expected task format:
        {
            'task': 'explore',
            'target': 'path/to/codebase',
            'question': 'What is the authentication system?',
            'scope': 'auth'  # optional: narrow the scope
        }
        """
        task_type = task.get('task', 'explore')
        target_path = task.get('target', '.')
        question = task.get('question', 'Explore the codebase structure')
        scope = task.get('scope', '')

        print(f"[{self.agent_id}] Exploring: {question}")
        print(f"[{self.agent_id}] Target: {target_path}")

        # Build context about the target
        context = await self._gather_context(target_path, scope)

        # Query Claude with the context and question
        prompt = f"""I need to explore a codebase to answer this question:
{question}

Target path: {target_path}
Scope: {scope if scope else 'Full codebase'}

Here's what I found in the codebase:

{context}

Please analyze this information and provide:
1. A summary of relevant findings
2. Key files and their purposes
3. Important patterns or architectural decisions
4. Potential challenges or constraints
5. Recommendations for the planner

Rate each finding by:
- Complexity (low/medium/high)
- Relevance (low/medium/high)
- Implementation cost (low/medium/high)
"""

        response = await self.query_claude(prompt)

        return {
            'question': question,
            'target': target_path,
            'context': context,
            'analysis': response,
            'timestamp': str(task.get('timestamp', ''))
        }

    async def _gather_context(self, target_path: str, scope: str = '') -> str:
        """
        Gather context about the target path.

        Args:
            target_path: Path to explore
            scope: Optional scope to narrow the search

        Returns:
            String containing structured context information
        """
        context_parts = []

        # Get directory structure
        context_parts.append("=== Directory Structure ===")
        try:
            structure = self._get_directory_tree(target_path, scope, max_depth=3)
            context_parts.append(structure)
        except Exception as e:
            context_parts.append(f"Error getting directory structure: {e}")

        # Find relevant files based on scope
        if scope:
            context_parts.append(f"\n=== Files matching scope '{scope}' ===")
            relevant_files = self._find_relevant_files(target_path, scope)
            for file_path in relevant_files[:20]:  # Limit to 20 files
                context_parts.append(f"  - {file_path}")

        # Get file counts by type
        context_parts.append("\n=== File Statistics ===")
        file_stats = self._get_file_statistics(target_path)
        for ext, count in sorted(file_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
            context_parts.append(f"  {ext}: {count} files")

        return "\n".join(context_parts)

    def _get_directory_tree(self, path: str, scope: str = '', max_depth: int = 3) -> str:
        """Get a tree representation of the directory structure."""
        lines = []
        path_obj = Path(path)

        def walk_dir(current_path: Path, prefix: str = "", depth: int = 0):
            if depth >= max_depth:
                return

            try:
                items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))

                # Filter by scope if provided
                if scope:
                    items = [item for item in items if scope.lower() in item.name.lower()]

                # Skip common ignore patterns
                ignore_patterns = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.eggs', 'build', 'dist'}
                items = [item for item in items if item.name not in ignore_patterns]

                for i, item in enumerate(items[:50]):  # Limit items
                    is_last = i == len(items) - 1
                    current_prefix = "└── " if is_last else "├── "
                    lines.append(f"{prefix}{current_prefix}{item.name}")

                    if item.is_dir():
                        extension = "    " if is_last else "│   "
                        walk_dir(item, prefix + extension, depth + 1)
            except PermissionError:
                lines.append(f"{prefix}[Permission Denied]")

        walk_dir(path_obj)
        return "\n".join(lines) if lines else "[Empty or inaccessible]"

    def _find_relevant_files(self, path: str, scope: str) -> list:
        """Find files relevant to the scope."""
        relevant_files = []
        path_obj = Path(path)

        for file_path in path_obj.rglob('*'):
            if file_path.is_file():
                # Check if scope appears in file name or path
                if scope.lower() in str(file_path).lower():
                    relevant_files.append(str(file_path.relative_to(path_obj)))

        return sorted(relevant_files)

    def _get_file_statistics(self, path: str) -> Dict[str, int]:
        """Get statistics about file types in the directory."""
        stats = {}
        path_obj = Path(path)

        for file_path in path_obj.rglob('*'):
            if file_path.is_file():
                ext = file_path.suffix if file_path.suffix else '[no extension]'
                stats[ext] = stats.get(ext, 0) + 1

        return stats
