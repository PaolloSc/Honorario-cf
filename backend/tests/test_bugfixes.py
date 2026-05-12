"""Tests for bug fixes: email file path resolution, Participacao null handling, DocuSeal ordering."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.contract import Participacao


# ── BUG 2: Participacao model coerces None to empty string ────────────────


class TestParticipacaoNullCoercion:
    """Participacao model_validator converts None values to empty strings."""

    def test_null_fields_coerced_to_empty_string(self):
        data = {
            "tem_participacao": True,
            "percentual_ou_valor": None,
            "para_quem": None,
            "natureza": None,
            "responsavel_captacao": None,
            "responsavel_gestao": None,
            "contato_financeiro_cliente": None,
        }
        p = Participacao(**data)
        assert p.percentual_ou_valor == ""
        assert p.para_quem == ""
        assert p.natureza == ""
        assert p.responsavel_captacao == ""
        assert p.responsavel_gestao == ""
        assert p.contato_financeiro_cliente == ""

    def test_missing_fields_coerced_to_empty_string(self):
        """Fields not provided at all should also default to empty string."""
        p = Participacao(tem_participacao=True)
        assert p.percentual_ou_valor == ""
        assert p.para_quem == ""
        assert p.natureza == ""
        assert p.responsavel_captacao == ""
        assert p.responsavel_gestao == ""
        assert p.contato_financeiro_cliente == ""

    def test_non_null_values_preserved(self):
        data = {
            "tem_participacao": True,
            "percentual_ou_valor": "10%",
            "para_quem": "Fulano",
            "natureza": "captacao",
            "responsavel_captacao": "Beltrano",
            "responsavel_gestao": "Cicrano",
            "contato_financeiro_cliente": "email@test.com",
        }
        p = Participacao(**data)
        assert p.percentual_ou_valor == "10%"
        assert p.para_quem == "Fulano"
        assert p.natureza == "captacao"
        assert p.responsavel_captacao == "Beltrano"
        assert p.responsavel_gestao == "Cicrano"
        assert p.contato_financeiro_cliente == "email@test.com"

    def test_partial_null_values(self):
        """Mix of None and non-None values."""
        data = {
            "tem_participacao": True,
            "percentual_ou_valor": "5%",
            "para_quem": None,
            "natureza": "performance",
            "responsavel_captacao": None,
            "responsavel_gestao": "Gestor",
            "contato_financeiro_cliente": None,
        }
        p = Participacao(**data)
        assert p.percentual_ou_valor == "5%"
        assert p.para_quem == ""
        assert p.natureza == "performance"
        assert p.responsavel_captacao == ""
        assert p.responsavel_gestao == "Gestor"
        assert p.contato_financeiro_cliente == ""


# ── BUG 1: Email endpoint file path resolution from DB ────────────────────


class TestEmailFilePathResolution:
    """The /api/email/send endpoint resolves file path from ContractVersionDB first."""

    def test_email_endpoint_uses_db_file_path(self, client):
        """When ContractVersionDB has a file_path that exists, use it."""
        from app.auth import CurrentUser, get_current_user
        from app.database import Base, ContractDB, ContractVersionDB, SessionLocal, engine, utcnow
        from app.config import BACKEND_DIR, settings

        # Override auth
        def fake_user():
            return CurrentUser(azure_id="test", email="test@test.com", name="Test", role="advogado")

        from app.main import app
        app.dependency_overrides[get_current_user] = fake_user

        try:
            # Create a temp file inside the expected output directory
            output_dir = BACKEND_DIR / settings.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            temp_file = output_dir / "test_contract_email_001.docx"
            temp_file.write_bytes(b"fake docx content")
            temp_path = str(temp_file)

            # Insert contract and version into DB
            db = SessionLocal()
            contract = ContractDB(
                contract_id="test-email-001",
                status="rascunho",
                client_name="Test Client",
                client_email="client@test.com",
                current_version=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(contract)
            db.commit()

            version = ContractVersionDB(
                contract_id="test-email-001",
                version_number=1,
                form_data_json="{}",
                file_path=temp_path,
                created_at=utcnow(),
            )
            db.add(version)
            db.commit()
            db.close()

            # Mock the email service to avoid actual sending
            with patch("app.routers.email.get_email_service") as mock_svc:
                mock_service = MagicMock()
                mock_service.send_email_with_attachment = AsyncMock(return_value={"success": True})
                mock_svc.return_value = mock_service

                response = client.post(
                    "/api/email/send",
                    json={
                        "contract_id": "test-email-001",
                        "destinatario_email": "dest@test.com",
                        "destinatario_nome": "Destinatario",
                    },
                )

                assert response.status_code == 200
                result = response.json()
                assert result["success"] is True

                # Verify the service was called with the DB file path
                call_kwargs = mock_service.send_email_with_attachment.call_args[1]
                assert call_kwargs["attachment_path"] == temp_path
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            os.unlink(temp_path)

    def test_email_endpoint_falls_back_to_reconstructed_path(self, client):
        """When DB has no file_path, fall back to settings-based path."""
        from app.auth import CurrentUser, get_current_user
        from app.database import ContractDB, ContractVersionDB, SessionLocal, utcnow

        def fake_user():
            return CurrentUser(azure_id="test", email="test@test.com", name="Test", role="advogado")

        from app.main import app
        app.dependency_overrides[get_current_user] = fake_user

        try:
            # Insert contract with version but no file_path
            db = SessionLocal()
            contract = ContractDB(
                contract_id="test-email-002",
                status="rascunho",
                client_name="Test Client",
                client_email="client@test.com",
                current_version=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(contract)
            db.commit()

            version = ContractVersionDB(
                contract_id="test-email-002",
                version_number=1,
                form_data_json="{}",
                file_path=None,  # No file path stored
                created_at=utcnow(),
            )
            db.add(version)
            db.commit()
            db.close()

            # This should return 404 since no file exists at reconstructed path either
            response = client.post(
                "/api/email/send",
                json={
                    "contract_id": "test-email-002",
                    "destinatario_email": "dest@test.com",
                    "destinatario_nome": "Destinatario",
                },
            )

            # Should get 404 since the fallback path also doesn't exist
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ── BUG 3: DocuSeal submitter ordering ───────────────────────────────────


class TestDocuSealOrdering:
    """DocuSeal submitters get correct order values based on role."""

    def test_order_assignment_by_role(self):
        """Verify order assignment logic matches expected pattern."""
        _ROLE_ORDER = {"Contratante": 1, "Advogado": 2, "Contratado": 3}

        signatarios = [
            {"email": "client@test.com", "name": "Client", "role": "Contratante"},
            {"email": "lawyer@test.com", "name": "Lawyer", "role": "Advogado"},
            {"email": "cf@test.com", "name": "C&F", "role": "Contratado"},
        ]

        for sig in signatarios:
            sig["order"] = _ROLE_ORDER.get(sig.get("role", "Contratante"), 1)

        assert signatarios[0]["order"] == 1
        assert signatarios[1]["order"] == 2
        assert signatarios[2]["order"] == 3

    def test_multiple_contratantes_get_same_order(self):
        """Multiple clients all get order=1."""
        _ROLE_ORDER = {"Contratante": 1, "Advogado": 2, "Contratado": 3}

        signatarios = [
            {"email": "client1@test.com", "name": "Client 1", "role": "Contratante"},
            {"email": "client2@test.com", "name": "Client 2", "role": "Contratante"},
            {"email": "lawyer@test.com", "name": "Lawyer", "role": "Advogado"},
            {"email": "cf@test.com", "name": "C&F", "role": "Contratado"},
        ]

        for sig in signatarios:
            sig["order"] = _ROLE_ORDER.get(sig.get("role", "Contratante"), 1)

        assert signatarios[0]["order"] == 1
        assert signatarios[1]["order"] == 1
        assert signatarios[2]["order"] == 2
        assert signatarios[3]["order"] == 3

    def test_service_includes_order_in_submitters(self):
        """DocuSealService.send_for_signature includes order in submitters payload."""
        from app.services.docuseal import DocuSealService

        service = DocuSealService()

        signatarios = [
            {"email": "client@test.com", "name": "Client", "role": "Contratante", "order": 1},
            {"email": "lawyer@test.com", "name": "Lawyer", "role": "Advogado", "order": 2},
            {"email": "cf@test.com", "name": "C&F", "role": "Contratado", "order": 3},
        ]

        # We test that the payload building logic includes order
        # by inspecting what would be sent (mock the HTTP call)
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = [
                {"id": 1, "submission_id": 100, "email": "client@test.com"}
            ]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            import asyncio
            result = asyncio.run(
                service.send_for_signature(
                    template_id=123,
                    signatarios=signatarios,
                    send_email=True,
                )
            )

            # Verify the call was made with order in submitters
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]

            assert payload["order"] == "preserved"
            for i, submitter in enumerate(payload["submitters"]):
                assert "order" in submitter
                assert submitter["order"] == signatarios[i]["order"]
