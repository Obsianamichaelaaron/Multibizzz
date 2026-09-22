from types import SimpleNamespace
from django.test import SimpleTestCase
from ml_engine.matcher import evaluate_applicant_qualification, calculate_skill_relevance


class QualificationThresholdTests(SimpleTestCase):
    def evaluate(self, applicant_skills, required_skills, exp=1, min_exp=1, education='Bachelor'):
        applicant = SimpleNamespace(
            get_skills_list=lambda: applicant_skills,
            experience_years=exp,
            education_level=education,
            employability_score=50.0,
            qualifications='',
            resume_file=None,
        )
        job = SimpleNamespace(
            skills_required=', '.join(required_skills),
            min_experience_years=min_exp,
            description='',
            requirements='',
        )
        return evaluate_applicant_qualification(applicant, job)

    def test_full_skill_match_is_very_strong_qualified(self):
        """Exact skill matches evaluate to high score and qualified status."""
        skills = ['Python', 'Django', 'PostgreSQL', 'Docker']
        result = self.evaluate(skills, skills)
        self.assertTrue(result['is_qualified'])
        self.assertEqual(result['qualification_status'], 'qualified')
        self.assertGreaterEqual(result['match_score'], 85.0)

    def test_transferable_skills_recognized(self):
        """Related skills like JavaScript -> React are recognized with transferable relevance."""
        score, rel_type, term = calculate_skill_relevance('react', {'javascript'})
        self.assertGreaterEqual(score, 0.80)
        self.assertEqual(rel_type, 'transferable')

        score2, rel_type2, term2 = calculate_skill_relevance('data analysis', {'microsoft excel'})
        self.assertGreaterEqual(score2, 0.80)
        self.assertEqual(rel_type2, 'transferable')

    def test_moderate_score_candidate_is_qualified(self):
        """Candidate with relevant transferable skills is Qualified even with moderate score (~60%)."""
        applicant_skills = ['JavaScript', 'HTML', 'CSS', 'Node.js']
        required_skills = ['React', 'TypeScript', 'Tailwind', 'Next.js']
        result = self.evaluate(applicant_skills, required_skills, exp=2, min_exp=2)
        self.assertTrue(result['is_qualified'])
        self.assertEqual(result['qualification_status'], 'qualified')
        self.assertGreaterEqual(result['match_score'], 55.0)

    def test_potentially_relevant_evaluated_for_review(self):
        """Candidate with partial/emerging relevance evaluates to under_qualified (for review)."""
        applicant_skills = ['HTML', 'CSS']
        required_skills = ['Python', 'Django', 'PostgreSQL', 'Docker', 'AWS', 'Celery']
        result = self.evaluate(applicant_skills, required_skills, exp=0, min_exp=2, education='High School')
        self.assertFalse(result['is_qualified'])
        self.assertEqual(result['qualification_status'], 'under_qualified')
        self.assertIn('For Review', result['reason'])

    def test_completely_unrelated_is_not_qualified(self):
        """Completely unrelated background with 0 transferable skills evaluates to not_qualified."""
        applicant_skills = ['Photoshop', 'Woodworking']
        required_skills = ['Java', 'Spring Boot', 'Kubernetes', 'Kafka', 'PostgreSQL']
        result = self.evaluate(applicant_skills, required_skills, exp=0, min_exp=3, education='High School')
        self.assertFalse(result['is_qualified'])
        self.assertEqual(result['qualification_status'], 'not_qualified')