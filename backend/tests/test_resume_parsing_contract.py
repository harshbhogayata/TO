from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import TalentProfile, User
from intelligence.models import ParsedResume


CANONICAL_KEYS = {
    'parsed_skills',
    'parsed_experience',
    'parsed_education',
    'generated_bio',
    'contact_info',
    'total_experience_years',
    'confidence_score',
    'parser_version',
    'ai_enhanced',
    'feature_flag_used',
    'cached',
}


class ResumeParsingContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='talent@example.com',
            password='StrongPass123!',
            full_name='Talent User',
            role='TALENT',
            is_verified=True,
        )
        TalentProfile.objects.create(
            user=self.user,
            bio='',
            location='Remote',
            skills=['python'],
            is_open_to_work=True,
        )
        self.client.force_authenticate(self.user)

    def _resume_file(self, name='resume.txt', content=b'Python engineer with React experience', content_type='text/plain'):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def _assert_canonical_contract(self, payload):
        self.assertTrue(CANONICAL_KEYS.issubset(payload.keys()), CANONICAL_KEYS - payload.keys())

    @patch('intelligence.nlp.parser.parse_resume')
    def test_authenticated_parse_returns_canonical_contract(self, mock_parse):
        mock_parse.return_value = {
            'skills': [{'canonical_name': 'python', 'confidence': 0.9, 'source': 'nlp'}],
            'experience': [{'title': 'Engineer'}],
            'education': [{'degree': 'BSc'}],
            'bio': 'Backend engineer',
            'contact': {'email': 'candidate@example.com'},
            'total_experience_years': 4.5,
            'confidence_score': 0.82,
            'parser_version': 'spacy_v1',
            'cached': False,
        }

        response = self.client.post(
            '/api/v1/intelligence/parse-resume/',
            {'resume': self._resume_file()},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self._assert_canonical_contract(response.json())
        self.assertEqual(response.json()['parsed_skills'][0]['canonical_name'], 'python')
        self.assertFalse(response.json()['ai_enhanced'])

    @override_settings(USE_AI_ENHANCED_RESUME_PARSING=True)
    @patch('intelligence.nlp.ai_enhanced_parser.parse_resume_ai_enhanced')
    def test_public_ai_parse_returns_canonical_contract_without_persistence(self, mock_parse):
        mock_parse.return_value = {
            'skills': [{'canonical_name': 'react', 'confidence': 0.96, 'source': 'ai_enhanced'}],
            'experience': [{'title': 'Frontend Engineer'}],
            'education': [],
            'bio': 'Frontend engineer',
            'contact': {'email': 'candidate@example.com'},
            'total_experience_years': 5.0,
            'confidence_score': 0.9,
            'parser_version': 'ai_enhanced_v1',
            'cached': False,
            'ai_enhanced': True,
        }

        self.client.force_authenticate(user=None)
        response = self.client.post(
            '/api/v1/intelligence/parse-resume-ai-public/',
            {'resume': self._resume_file()},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._assert_canonical_contract(response.json())
        self.assertTrue(response.json()['ai_enhanced'])
        self.assertEqual(response.json()['feature_flag_used'], 'USE_AI_ENHANCED_RESUME_PARSING')
        self.assertEqual(ParsedResume.objects.count(), 0)

    @override_settings(USE_AI_ENHANCED_RESUME_PARSING=False)
    @patch('intelligence.nlp.parser.parse_resume')
    def test_feature_flag_disabled_ai_endpoint_falls_back_with_same_contract(self, mock_parse):
        mock_parse.return_value = {
            'skills': ['python'],
            'experience': [],
            'education': [],
            'bio': 'Python engineer',
            'contact': {'name': 'Candidate'},
            'total_experience_years': 3.0,
            'confidence_score': 0.7,
            'parser_version': 'spacy_v1',
            'cached': False,
        }

        self.client.force_authenticate(user=None)
        response = self.client.post(
            '/api/v1/intelligence/parse-resume-ai-public/',
            {'resume': self._resume_file()},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._assert_canonical_contract(response.json())
        self.assertFalse(response.json()['ai_enhanced'])
        self.assertIsNone(response.json()['feature_flag_used'])

    def test_invalid_file_type_rejected(self):
        response = self.client.post(
            '/api/v1/intelligence/parse-resume-public/',
            {'resume': self._resume_file(name='resume.exe', content_type='application/octet-stream')},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_resume_rejected(self):
        response = self.client.post(
            '/api/v1/intelligence/parse-resume-public/',
            {'resume': self._resume_file(content=b'a' * (10 * 1024 * 1024 + 1))},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
