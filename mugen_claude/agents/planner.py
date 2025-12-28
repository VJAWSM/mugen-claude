"""
Planner Agent - Creates implementation plans based on exploration results.
"""
from typing import Dict, Any, List
import json

from .base import BaseAgent
from ..coordination import AgentMessage


class PlannerAgent(BaseAgent):
    """
    Planner Agent specializes in:
    - Creating detailed implementation plans
    - Breaking down complex problems into tasks
    - Asking Explorer for additional context
    - Identifying required resources and dependencies
    - Determining agent types needed for implementation
    - Defining task breakdown with implementation details
    """

    def get_system_prompt(self) -> str:
        return """You are an Expert System Architect and Implementation Planner.

Your role is to create detailed, actionable implementation plans based on problem descriptions and context provided by the Explorer agent.

Your capabilities:
1. Analyze complex problems and break them into manageable tasks
2. Ask the Explorer agent for specific information you need
3. Identify dependencies and execution order
4. Determine which specialized agents are needed (e.g., Java agent, Python agent, Frontend agent)
5. Create detailed implementation steps with file-level granularity
6. Assess complexity, risk, and resource requirements
7. Define acceptance criteria for each task

When creating plans:
- Be specific about files, functions, and components to modify
- Break tasks into atomic, independent units where possible
- Identify parallel work opportunities
- Highlight potential risks and mitigation strategies
- Specify which specialized agent type should handle each task
- Include testing and validation steps

Always output structured plans in a clear, hierarchical format that can be executed by other agents.

Plan structure should include:
1. Overview and objectives
2. Required agent types (if new types need to be created)
3. Task breakdown with:
   - Task ID
   - Description
   - Dependencies (other task IDs)
   - Files to modify
   - Agent type required
   - Complexity estimate
   - Acceptance criteria
4. Risk assessment
5. Validation strategy"""

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a planning task.

        Expected task format:
        {
            'task': 'plan',
            'problem': 'Description of what needs to be built',
            'context': 'Initial context (optional)',
            'explorer_id': 'ID of explorer agent to query'
        }
        """
        problem = task.get('problem', '')
        initial_context = task.get('context', '')
        explorer_id = task.get('explorer_id', None)

        print(f"[{self.agent_id}] Planning for: {problem[:100]}...")

        # Phase 1: Analyze the problem and identify information needs
        analysis_prompt = f"""I need to create an implementation plan for the following problem:

{problem}

Initial context:
{initial_context}

First, analyze this problem and:
1. Identify what additional information you need to create a complete plan
2. List specific questions to ask the Explorer agent
3. Outline the high-level approach

Format your response as:
INFORMATION NEEDS:
[List of specific questions for the Explorer]

HIGH-LEVEL APPROACH:
[Brief outline of the approach]
"""

        analysis = await self.query_claude(analysis_prompt)
        print(f"[{self.agent_id}] Initial analysis complete")

        # Phase 2: Query Explorer for additional context if available
        explorer_responses = []
        if explorer_id and "INFORMATION NEEDS:" in analysis:
            questions = self._extract_questions(analysis)
            print(f"[{self.agent_id}] Asking Explorer {len(questions)} questions")

            for question in questions[:5]:  # Limit to 5 questions
                # Send query to explorer
                self.send_message(
                    explorer_id,
                    'query',
                    {'question': question}
                )

                # Wait for response (with timeout)
                response = await self._wait_for_response(explorer_id, timeout=30)
                if response:
                    explorer_responses.append({
                        'question': question,
                        'answer': response.content.get('answer', 'No response')
                    })

        # Phase 3: Create detailed plan
        plan_prompt = f"""Based on the problem and gathered information, create a detailed implementation plan.

PROBLEM:
{problem}

INITIAL ANALYSIS:
{analysis}

EXPLORER FINDINGS:
{json.dumps(explorer_responses, indent=2) if explorer_responses else 'No additional information gathered'}

Create a comprehensive implementation plan with the following structure:

1. OVERVIEW
   - Objectives
   - Success criteria

2. REQUIRED AGENT TYPES
   - List any specialized agent types needed (e.g., "java-agent", "react-agent")
   - For each, describe its purpose and required capabilities

3. TASK BREAKDOWN
   For each task, provide:
   - task_id: Unique identifier (e.g., "T001")
   - description: What needs to be done
   - dependencies: List of task IDs that must complete first (e.g., ["T001", "T002"])
   - files: List of files to create/modify
   - agent_type: Which agent type should handle this (e.g., "executor", "java-agent")
   - complexity: low/medium/high
   - estimated_effort: small/medium/large
   - acceptance_criteria: How to verify completion

4. RISKS AND MITIGATIONS
   - Identify potential risks
   - Suggest mitigation strategies

5. VALIDATION STRATEGY
   - Testing approach
   - Integration verification

Format the task breakdown as a JSON array for easy parsing by the orchestrator.
"""

        plan = await self.query_claude(plan_prompt)
        print(f"[{self.agent_id}] Detailed plan created")

        # Extract structured task breakdown if possible
        tasks = self._extract_tasks(plan)

        return {
            'problem': problem,
            'analysis': analysis,
            'explorer_responses': explorer_responses,
            'plan': plan,
            'structured_tasks': tasks,
            'requires_new_agents': self._extract_required_agents(plan)
        }

    async def _wait_for_response(self, from_agent: str, timeout: float = 30) -> AgentMessage:
        """Wait for a response from another agent."""
        import asyncio
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            msg = self.receive_message(timeout=0.5)
            if msg and msg.from_agent == from_agent and msg.message_type == 'response':
                return msg
            await asyncio.sleep(0.5)

        return None

    def _extract_questions(self, analysis: str) -> List[str]:
        """Extract questions from the analysis text."""
        questions = []
        lines = analysis.split('\n')
        in_questions_section = False

        for line in lines:
            if 'INFORMATION NEEDS:' in line:
                in_questions_section = True
                continue
            if in_questions_section:
                if line.strip().startswith('-') or line.strip().startswith('•'):
                    question = line.strip().lstrip('-•').strip()
                    if question:
                        questions.append(question)
                elif line.strip() and line.strip()[0].isupper() and ':' in line:
                    # New section started
                    break

        return questions

    def _extract_tasks(self, plan: str) -> List[Dict[str, Any]]:
        """
        Try to extract structured tasks from the plan.
        Looks for JSON array in the plan text.
        """
        try:
            # Look for JSON array in the plan
            start_idx = plan.find('[')
            end_idx = plan.rfind(']')

            if start_idx != -1 and end_idx != -1:
                json_str = plan[start_idx:end_idx + 1]
                tasks = json.loads(json_str)
                if isinstance(tasks, list):
                    return tasks
        except Exception as e:
            print(f"[{self.agent_id}] Could not extract structured tasks: {e}")

        return []

    def _extract_required_agents(self, plan: str) -> List[str]:
        """Extract list of required specialized agent types from the plan."""
        required_agents = []

        # Look for common agent type patterns
        agent_patterns = [
            'java-agent', 'python-agent', 'javascript-agent', 'typescript-agent',
            'react-agent', 'vue-agent', 'angular-agent',
            'rust-agent', 'go-agent', 'cpp-agent',
            'sql-agent', 'frontend-agent', 'backend-agent', 'api-agent',
            'test-agent', 'devops-agent'
        ]

        plan_lower = plan.lower()
        for agent_type in agent_patterns:
            if agent_type in plan_lower:
                required_agents.append(agent_type)

        return list(set(required_agents))  # Remove duplicates
