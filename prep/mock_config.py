# Settings for mock tests. Change the numbers here to change the tests.
#
# Each section is: (subject name, number of questions, minutes)
# The subject name must match a Subject name in the admin panel exactly.

NEGATIVE_MARK = 0.25          # marks lost for each wrong answer (1 mark per right answer)

# Share of Easy / Medium / Hard questions in each section
DIFFICULTY_MIX = {"Easy": 0.4, "Medium": 0.4, "Hard": 0.2}

PRESETS = {
    "mini": {
        "name": "Mini mock",
        "description": "A short test to try the system: 5 questions and 5 minutes per section.",
        "sections": [
            ("English Language", 5, 5),
            ("Quantitative Aptitude", 5, 5),
            ("Reasoning Ability", 5, 5),
        ],
    },
}