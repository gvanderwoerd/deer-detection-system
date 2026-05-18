"""
Claude Model Recommendation System
Analyzes tasks and recommends the most appropriate Claude model
"""

from enum import Enum
from typing import Dict, List, Tuple


class ClaudeModel(Enum):
    """Available Claude models with their characteristics"""
    HAIKU = {
        "name": "Haiku (claude-haiku-4-5-20251001)",
        "strengths": [
            "Fast, straightforward tasks",
            "Simple documentation reading",
            "Quick summaries and data retrieval",
            "Basic code analysis",
            "Real-time responses needed"
        ],
        "latency": "~200ms",
        "cost": "Lowest",
        "ideal_for": "Quick tasks, simple comprehension, fast feedback"
    }
    SONNET = {
        "name": "Sonnet 4.5 (claude-sonnet-4-5-20250929)",
        "strengths": [
            "Balanced performance",
            "Code implementation",
            "Complex problem solving",
            "API design",
            "General-purpose tasks"
        ],
        "latency": "~500ms",
        "cost": "Medium",
        "ideal_for": "Most development tasks, good speed/quality balance"
    }
    OPUS = {
        "name": "Opus 4.6 (claude-opus-4-6)",
        "strengths": [
            "Most capable reasoning",
            "Complex architectural decisions",
            "Edge cases and nuance",
            "Advanced problem analysis",
            "Security reviews"
        ],
        "latency": "~2s",
        "cost": "Highest",
        "ideal_for": "Complex reasoning, critical decisions, research"
    }


class TaskCategory(Enum):
    """Categories of tasks for model selection"""
    DOCUMENTATION_REVIEW = "documentation_review"
    CODE_IMPLEMENTATION = "code_implementation"
    DEBUGGING = "debugging"
    ARCHITECTURE = "architecture"
    QUICK_LOOKUP = "quick_lookup"
    COMPLEX_ANALYSIS = "complex_analysis"
    TESTING = "testing"


class ModelRecommender:
    """Recommends optimal Claude model for different task types"""

    # Task category to model mapping
    TASK_MODEL_MAP: Dict[TaskCategory, ClaudeModel] = {
        TaskCategory.QUICK_LOOKUP: ClaudeModel.HAIKU,
        TaskCategory.DOCUMENTATION_REVIEW: ClaudeModel.HAIKU,
        TaskCategory.CODE_IMPLEMENTATION: ClaudeModel.SONNET,
        TaskCategory.TESTING: ClaudeModel.HAIKU,
        TaskCategory.DEBUGGING: ClaudeModel.SONNET,
        TaskCategory.ARCHITECTURE: ClaudeModel.OPUS,
        TaskCategory.COMPLEX_ANALYSIS: ClaudeModel.OPUS,
    }

    # Keywords that indicate task type
    TASK_KEYWORDS: Dict[TaskCategory, List[str]] = {
        TaskCategory.QUICK_LOOKUP: [
            "find", "search", "where", "which file", "list", "show",
            "what is", "grep", "locate", "browse"
        ],
        TaskCategory.DOCUMENTATION_REVIEW: [
            "read", "review", "summarize", "understand", "explain",
            "document", "docs", "guide", "manual", "get up to speed"
        ],
        TaskCategory.CODE_IMPLEMENTATION: [
            "implement", "add feature", "write", "create", "modify",
            "build", "develop", "code", "function", "method"
        ],
        TaskCategory.DEBUGGING: [
            "debug", "fix", "error", "bug", "issue", "not working",
            "crash", "fail", "problem", "broken"
        ],
        TaskCategory.ARCHITECTURE: [
            "architecture", "design", "refactor", "structure", "pattern",
            "scalability", "performance", "optimization", "plan", "approach"
        ],
        TaskCategory.COMPLEX_ANALYSIS: [
            "analyze", "research", "investigate", "deep dive",
            "complex", "critical", "security", "assessment"
        ],
        TaskCategory.TESTING: [
            "test", "unit test", "integration test", "verify", "validate",
            "check", "ensure", "confirm"
        ]
    }

    @classmethod
    def detect_task_category(cls, task_description: str) -> Tuple[TaskCategory, float]:
        """
        Detect the category of a task from its description.
        Returns (category, confidence_score)
        """
        task_lower = task_description.lower()

        # Score each category
        scores = {}
        for category, keywords in cls.TASK_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in task_lower)
            scores[category] = score

        # Find category with highest score
        if not scores or max(scores.values()) == 0:
            # Default to Sonnet for unknown tasks
            return TaskCategory.CODE_IMPLEMENTATION, 0.5

        best_category = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_category] / 3.0)  # Normalize to 0-1

        return best_category, confidence

    @classmethod
    def recommend_model(cls, task_description: str) -> Dict:
        """
        Recommend the best Claude model for a task.

        Returns:
            {
                "recommended_model": ClaudeModel,
                "task_category": TaskCategory,
                "confidence": float (0.0-1.0),
                "reasoning": str,
                "model_info": dict,
                "should_switch": bool
            }
        """
        category, confidence = cls.detect_task_category(task_description)
        recommended_model = cls.TASK_MODEL_MAP[category]
        model_info = recommended_model.value

        reasoning = cls._generate_reasoning(category, model_info)

        return {
            "recommended_model": recommended_model.name,
            "task_category": category.value,
            "confidence": confidence,
            "reasoning": reasoning,
            "model_info": {
                "name": model_info["name"],
                "strengths": model_info["strengths"],
                "latency": model_info["latency"],
                "cost": model_info["cost"],
                "ideal_for": model_info["ideal_for"]
            },
            "should_switch": True  # Server should evaluate current model
        }

    @classmethod
    def check_model_appropriateness(cls, task_description: str, current_model: str) -> Dict:
        """
        Check if current model is appropriate for the task.

        Returns:
            {
                "is_appropriate": bool,
                "recommended_model": str,
                "reason": str,
                "benefit_of_switching": str or None
            }
        """
        recommendation = cls.recommend_model(task_description)
        recommended = recommendation["recommended_model"]

        is_appropriate = current_model.lower() == recommended.lower()

        result = {
            "is_appropriate": is_appropriate,
            "recommended_model": recommended,
            "reason": recommendation["reasoning"],
        }

        if not is_appropriate:
            result["benefit_of_switching"] = cls._get_switch_benefit(
                current_model, recommended, recommendation["task_category"]
            )

        return result

    @staticmethod
    def _generate_reasoning(category: TaskCategory, model_info: Dict) -> str:
        """Generate human-readable reasoning for model recommendation"""
        reasons = {
            TaskCategory.QUICK_LOOKUP:
                f"Quick lookup task - {model_info['ideal_for']}",
            TaskCategory.DOCUMENTATION_REVIEW:
                f"Documentation reading - {model_info['ideal_for']}",
            TaskCategory.CODE_IMPLEMENTATION:
                f"Code implementation - {model_info['ideal_for']}",
            TaskCategory.DEBUGGING:
                f"Debugging task - {model_info['ideal_for']}",
            TaskCategory.ARCHITECTURE:
                f"Architectural decision - {model_info['ideal_for']}",
            TaskCategory.COMPLEX_ANALYSIS:
                f"Complex analysis - {model_info['ideal_for']}",
            TaskCategory.TESTING:
                f"Testing task - {model_info['ideal_for']}"
        }
        return reasons.get(category, "Task analysis recommended")

    @staticmethod
    def _get_switch_benefit(current: str, recommended: str, task_category: str) -> str:
        """Explain the benefit of switching models"""
        if "haiku" in recommended.lower() and "haiku" not in current.lower():
            return "Faster response, lower latency - ideal for simple tasks"
        elif "opus" in recommended.lower() and "opus" not in current.lower():
            return "Better reasoning for complex problems, handles edge cases better"
        elif "sonnet" in recommended.lower() and "sonnet" not in current.lower():
            return "Balanced performance improvement for this task type"
        return "Better optimized for this task type"


def get_model_recommendation_api(task_description: str, current_model: str = None) -> Dict:
    """
    API endpoint helper - returns model recommendation as JSON

    Args:
        task_description: Description of the task to analyze
        current_model: Current Claude model in use (optional)

    Returns:
        JSON-serializable dictionary with recommendation
    """
    recommendation = ModelRecommender.recommend_model(task_description)

    if current_model:
        appropriateness = ModelRecommender.check_model_appropriateness(
            task_description, current_model
        )
        recommendation.update(appropriateness)

    return recommendation
