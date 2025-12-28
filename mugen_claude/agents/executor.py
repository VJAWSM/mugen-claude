"""
Executor Agent - Executes implementation tasks from plans.
"""
import os
from typing import Dict, Any
from pathlib import Path

from .base import BaseAgent
from ..coordination import file_lock


class ExecutorAgent(BaseAgent):
    """
    Executor Agent specializes in:
    - Implementing code based on task specifications
    - Modifying existing files
    - Creating new files
    - Running tests and validations
    - Coordinating with other executors via file locking
    - Reporting implementation status
    """

    def get_system_prompt(self) -> str:
        return """You are an Expert Software Developer and Implementation Agent.

Your role is to execute implementation tasks by writing, modifying, and testing code according to specifications provided in the task.

Your capabilities:
1. Write clean, maintainable, well-documented code
2. Modify existing files while preserving compatibility
3. Create new files with proper structure
4. Follow existing code patterns and conventions
5. Implement proper error handling and edge cases
6. Write tests to validate implementations
7. Coordinate with other executors to avoid conflicts

When implementing:
- Read existing code to understand patterns and conventions
- Use file locking when modifying files to prevent conflicts
- Write clear, self-documenting code
- Include error handling and edge cases
- Follow the language's best practices
- Add appropriate comments for complex logic
- Verify your implementation meets acceptance criteria

Always respond with:
1. Summary of what was implemented
2. Files created/modified
3. Key decisions made
4. Any issues or concerns
5. Validation results

If you encounter a file that's locked by another agent, wait and retry or report the conflict."""

    def get_allowed_tools(self) -> str:
        """Executor agents can read, write, edit files and run commands."""
        return "Read,Write,Edit,Bash"

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an implementation task.

        Expected task format:
        {
            'task': 'implement',
            'task_id': 'T001',
            'description': 'Implement user authentication',
            'files': ['src/auth.py', 'tests/test_auth.py'],
            'specifications': 'Detailed specs...',
            'acceptance_criteria': ['Criterion 1', 'Criterion 2'],
            'working_directory': '/path/to/project'
        }
        """
        task_id = task.get('task_id', 'unknown')
        description = task.get('description', '')
        files = task.get('files', [])
        specifications = task.get('specifications', '')
        acceptance_criteria = task.get('acceptance_criteria', [])
        working_dir = task.get('working_directory', '.')

        print(f"[{self.agent_id}] Executing task {task_id}: {description}")

        # Read existing files to understand context
        file_contexts = {}
        for file_path in files:
            full_path = os.path.join(working_dir, file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r') as f:
                        file_contexts[file_path] = f.read()
                    print(f"[{self.agent_id}] Read existing file: {file_path}")
                except Exception as e:
                    print(f"[{self.agent_id}] Could not read {file_path}: {e}")
                    file_contexts[file_path] = f"[Could not read: {e}]"
            else:
                file_contexts[file_path] = "[New file]"
                print(f"[{self.agent_id}] Will create new file: {file_path}")

        # Build implementation prompt
        context_str = "\n\n".join([
            f"=== {path} ===\n{content[:2000]}{'...' if len(content) > 2000 else ''}"
            for path, content in file_contexts.items()
        ])

        implementation_prompt = f"""I need to implement the following task:

TASK ID: {task_id}
DESCRIPTION: {description}

SPECIFICATIONS:
{specifications}

ACCEPTANCE CRITERIA:
{chr(10).join(f"- {criterion}" for criterion in acceptance_criteria)}

EXISTING FILES:
{context_str}

WORKING DIRECTORY: {working_dir}

Please provide:
1. Complete implementation for each file
2. Explanation of key decisions
3. How each acceptance criterion is met
4. Any potential issues or limitations

Format each file implementation as:
```filename: path/to/file.ext
[complete file content]
```

After all implementations, provide a summary.
"""

        # Get implementation from Claude
        implementation = await self.query_claude(implementation_prompt)
        print(f"[{self.agent_id}] Implementation generated")

        # Parse and write files
        written_files = []
        errors = []

        file_implementations = self._extract_file_implementations(implementation)

        for file_path, content in file_implementations.items():
            full_path = os.path.join(working_dir, file_path)

            try:
                # Acquire file lock
                print(f"[{self.agent_id}] Acquiring lock for {file_path}")
                if not self.coordination.acquire_file_lock(self.agent_id, full_path):
                    error_msg = f"Could not acquire lock for {file_path} (locked by another agent)"
                    print(f"[{self.agent_id}] {error_msg}")
                    errors.append(error_msg)
                    continue

                # Create directory if needed
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                # Write file
                with open(full_path, 'w') as f:
                    f.write(content)

                written_files.append(file_path)
                print(f"[{self.agent_id}] Wrote file: {file_path}")

                # Release lock
                self.coordination.release_file_lock(self.agent_id, full_path)

            except Exception as e:
                error_msg = f"Error writing {file_path}: {str(e)}"
                print(f"[{self.agent_id}] {error_msg}")
                errors.append(error_msg)
                # Release lock if we had it
                self.coordination.release_file_lock(self.agent_id, full_path)

        # Run validation if specified
        validation_results = []
        if acceptance_criteria:
            validation_prompt = f"""The implementation is complete. Verify if it meets these acceptance criteria:

{chr(10).join(f"- {criterion}" for criterion in acceptance_criteria)}

For each criterion, state whether it's met and why.
"""
            validation = await self.query_claude(validation_prompt)
            validation_results.append(validation)

        return {
            'task_id': task_id,
            'description': description,
            'implementation': implementation,
            'written_files': written_files,
            'errors': errors,
            'validation': validation_results,
            'success': len(errors) == 0 and len(written_files) > 0
        }

    def _extract_file_implementations(self, implementation: str) -> Dict[str, str]:
        """
        Extract file implementations from Claude's response.
        Looks for code blocks with filename annotations.
        """
        file_implementations = {}
        lines = implementation.split('\n')
        current_file = None
        current_content = []

        for line in lines:
            # Look for filename markers
            if line.startswith('```') and 'filename:' in line.lower():
                # Save previous file if any
                if current_file and current_content:
                    file_implementations[current_file] = '\n'.join(current_content)
                    current_content = []

                # Extract filename
                parts = line.split('filename:', 1)
                if len(parts) > 1:
                    current_file = parts[1].strip().strip('`').strip()
                continue

            elif line.startswith('```') and current_file:
                # End of code block
                if current_content:
                    file_implementations[current_file] = '\n'.join(current_content)
                current_file = None
                current_content = []
                continue

            elif current_file:
                # Accumulate content
                current_content.append(line)

        # Save last file if any
        if current_file and current_content:
            file_implementations[current_file] = '\n'.join(current_content)

        return file_implementations
