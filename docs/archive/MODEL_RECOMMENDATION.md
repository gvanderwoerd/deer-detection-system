# Claude Model Recommendation System

**Added:** 2026-05-18
**Feature:** Automatic Claude model recommendation based on task type

---

## Overview

The deer detection system now includes a **Claude Model Recommendation Engine** that analyzes tasks and recommends the most appropriate Claude model for the job.

This helps ensure optimal performance by using:
- **Haiku** for quick, straightforward tasks
- **Sonnet** for balanced code implementation
- **Opus** for complex reasoning and architectural decisions

---

## API Endpoint

### POST `/api/model-recommendation`

Analyzes a task description and recommends the best Claude model.

**Request:**
```json
{
  "task_description": "Read and understand the project documentation",
  "current_model": "sonnet"  // optional
}
```

**Response:**
```json
{
  "success": true,
  "recommendation": {
    "recommended_model": "haiku",
    "task_category": "documentation_review",
    "confidence": 0.9,
    "reasoning": "Documentation reading - Quick tasks, simple comprehension, fast feedback",
    "is_appropriate": false,
    "benefit_of_switching": "Faster response, lower latency - ideal for simple tasks",
    "model_info": {
      "name": "Haiku (claude-haiku-4-5-20251001)",
      "strengths": [
        "Fast, straightforward tasks",
        "Simple documentation reading",
        ...
      ],
      "latency": "~200ms",
      "cost": "Lowest",
      "ideal_for": "Quick tasks, simple comprehension, fast feedback"
    }
  }
}
```

---

## Task Categories & Model Recommendations

| Category | Best Model | Use Case |
|----------|-----------|----------|
| Quick Lookup | **Haiku** | Finding files, searching code, listing information |
| Documentation Review | **Haiku** | Reading guides, understanding existing code |
| Code Implementation | **Sonnet** | Writing features, implementing functions |
| Debugging | **Sonnet** | Fixing bugs, analyzing errors |
| Testing | **Haiku** | Unit tests, test verification |
| Architecture | **Opus** | System design, refactoring, optimization |
| Complex Analysis | **Opus** | Security reviews, deep investigation |

---

## Claude Models Overview

### Haiku (claude-haiku-4-5-20251001)
- **Latency:** ~200ms (fastest)
- **Cost:** Lowest
- **Best For:** Quick tasks, simple comprehension, documentation reading
- **Strengths:**
  - Straightforward problem solving
  - Fast responses (ideal for real-time needs)
  - Simple data retrieval and lookup
  - Basic code analysis
  - Cost-effective for simple tasks

### Sonnet 4.5 (claude-sonnet-4-5-20250929)
- **Latency:** ~500ms (balanced)
- **Cost:** Medium
- **Best For:** Most development tasks
- **Strengths:**
  - Code implementation and debugging
  - Complex problem solving with good speed
  - API design and general-purpose tasks
  - Good balance of capability and speed

### Opus 4.6 (claude-opus-4-6) - Most Capable
- **Latency:** ~2s (slowest)
- **Cost:** Highest
- **Best For:** Complex reasoning and critical decisions
- **Strengths:**
  - Most advanced reasoning
  - Complex architectural decisions
  - Edge case analysis
  - Advanced problem analysis
  - Security reviews and deep investigation

---

## Implementation Details

### Location
- **Module:** `server/model_recommendation.py`
- **Integration:** `server/main.py` (new API endpoint)

### How It Works

1. **Task Detection:** Analyzes task description using keyword matching
2. **Categorization:** Maps task to one of 7 categories
3. **Model Selection:** Recommends model from TASK_MODEL_MAP
4. **Confidence Scoring:** Returns 0.0-1.0 confidence score
5. **Appropriateness Check:** Compares against current model (if provided)

### Keyword-Based Detection

The system identifies task types through keywords:

```python
# Example keywords for each category:
QUICK_LOOKUP: ["find", "search", "where", "grep", "locate"]
DOCUMENTATION_REVIEW: ["read", "review", "summarize", "understand"]
CODE_IMPLEMENTATION: ["implement", "write", "create", "build"]
DEBUGGING: ["debug", "fix", "error", "bug", "broken"]
ARCHITECTURE: ["design", "refactor", "pattern", "optimization"]
COMPLEX_ANALYSIS: ["analyze", "research", "security", "critical"]
TESTING: ["test", "verify", "validate", "check"]
```

---

## Usage Examples

### Example 1: Documentation Review Task
```bash
curl -X POST http://localhost:5000/api/model-recommendation \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Read and understand the ESP32 firmware notes",
    "current_model": "sonnet"
  }'
```

**Result:** Recommends **Haiku** (faster, simpler task)

### Example 2: Architecture Planning
```bash
curl -X POST http://localhost:5000/api/model-recommendation \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Design a new detection architecture with caching and optimization",
    "current_model": "sonnet"
  }'
```

**Result:** Recommends **Opus** (complex reasoning needed)

### Example 3: Bug Fix
```bash
curl -X POST http://localhost:5000/api/model-recommendation \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Debug the detection not working when PIR motion is triggered"
  }'
```

**Result:** Recommends **Sonnet** (debugging task)

---

## Integration with Claude Code

The model recommendation system works with Claude Code to suggest model changes:

1. **Proactive Detection:** Claude Code should invoke the API when starting a task
2. **User Notification:** Suggest `/model haiku|sonnet|opus` if current model is suboptimal
3. **Context Awareness:** Analyzes the actual work being performed
4. **Performance Optimization:** Faster responses for simple tasks, better reasoning for complex ones

---

## Benefits

✅ **Performance:** Use fastest model appropriate for task
✅ **Cost Efficiency:** Avoid expensive models for simple tasks
✅ **Quality:** Use most capable model for critical decisions
✅ **Automation:** Suggestions reduce manual model switching
✅ **Learning:** System learns which tasks need which models

---

## Future Enhancements

Potential improvements:
- [ ] Machine learning to improve keyword detection
- [ ] User feedback to refine recommendations
- [ ] Task complexity scoring (0-100)
- [ ] Time/cost estimation based on task
- [ ] Historical tracking of model effectiveness
- [ ] Integration with Claude Code slash commands

---

## Technical Notes

- **Keyword Matching:** Simple but effective for most task types
- **Confidence Scoring:** Based on keyword match count
- **Extensible:** Easy to add new task categories or models
- **Stateless:** Each request is independent
- **Logging:** Recommendations logged for analysis

---

## Testing the Feature

### Start the Server
```bash
cd /mnt/linux-data/deer-detection-system
./start.sh
```

### Test the API
```bash
# Quick lookup task (should recommend Haiku)
curl -X POST http://localhost:5000/api/model-recommendation \
  -H "Content-Type: application/json" \
  -d '{"task_description": "Find where the detection code is located"}'

# Implementation task (should recommend Sonnet)
curl -X POST http://localhost:5000/api/model-recommendation \
  -H "Content-Type: application/json" \
  -d '{"task_description": "Add a new detection class for raccoons"}'

# Architecture task (should recommend Opus)
curl -X POST http://localhost:5000/api/model-recommendation \
  -H "Content-Type: application/json" \
  -d '{"task_description": "Redesign the detection system for better performance and scalability"}'
```

---

**Built as part of automated model optimization initiative - 2026-05-18**
