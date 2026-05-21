"""Comprehensive tests for the send-for-signature flow.

Tests cover:
1. Unit tests for _resolve_contract_filepath (path resolution strategies)
2. Integration tests for POST /api/docuseal/send-for-signature endpoint
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth import CurrentUser, get_current_user
from app.config import BACKEND_DIR, settings
from app.database import ContractDB, ContractVersionDB, SessionLocal, utcnow
from app.main import app
from app.routers.docuseal import _resolve_contract_filepath


# ── Helpers ────────────────────────────────────────────────────────────────


def _fake_user():
    return CurrentUser(
        azure_id="test-azure-id",
        email="lawyer@test.com",
        name="Test Lawyer",
        role="advogado",
    )


def _get_output_dir() -> Path:
    """Return the resolved output directory for contracts."""
    from app.routers.docuseal import resolve_backend_path
    return resolve_backend_path(settings.output_dir)


def _create_contract_in_db(
    db,
    contract_id: str,
    file_path=None,
    form_data_json="{}",
    client_name="Test Client",
    client_email="client@test.com",
):
    """Helper to insert a contract and version into DB."""
    contract = ContractDB(
        contract_id=contract_id,
        status="rascunho",
        client_name=client_name,
        client_email=client_email,
        current_version=1,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(contract)
    db.commit()

    version = ContractVersionDB(
        contract_id=contract_id,
        version_number=1,
        form_data_json=form_data_json,
        file_path=file_path,
        created_at=utcnow(),
    )
    db.add(version)
    db.commit()
    return contract, version


# ── 1. Unit tests for _resolve_contract_filepath ──────────────────────────


class TestResolveContractFilepath:
    """Unit tests for the _resolve_contract_filepath function."""

    def test_resolve_finds_file_at_stored_path(self):
        """Strategy 1: file exists at the exact stored path in DB."""
        db = SessionLocal()
        try:
            output_dir = _get_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create a real temp file
            temp_file = output_dir / "stored_path_test.docx"
            temp_file.write_bytes(b"fake docx content")

            contract_id = "resolve-stored-001"
            _create_contract_in_db(db, contract_id, file_path=str(temp_file))

            result = _resolve_contract_filepath(contract_id, db)
            assert result == temp_file
        finally:
            db.close()
            if temp_file.exists():
                temp_file.unlink()

    def test_resolve_finds_file_at_reconstructed_path(self):
        """Strategy 2: stored path doesn't exist, but filename found in output_dir."""
        db = SessionLocal()
        try:
            output_dir = _get_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)

            # The stored path references a non-existent directory
            filename = "contrato_reconstructed_test.docx"
            stored_path = f"/old/deploy/generated_contracts/{filename}"

            # But the file exists in current output_dir
            real_file = output_dir / filename
            real_file.write_bytes(b"fake docx content")

            contract_id = "resolve-reconstructed-001"
            _create_contract_in_db(db, contract_id, file_path=stored_path)

            result = _resolve_contract_filepath(contract_id, db)
            assert result == real_file
        finally:
            db.close()
            if real_file.exists():
                real_file.unlink()

    def test_resolve_finds_file_at_convention_fallback(self):
        """Strategy 3: no file_path in DB, but convention file exists in output_dir."""
        db = SessionLocal()
        try:
            output_dir = _get_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)

            contract_id = "resolve-fallback-001"
            fallback_file = output_dir / f"contrato_{contract_id}.docx"
            fallback_file.write_bytes(b"fake docx content")

            # Create contract version with file_path=None
            _create_contract_in_db(db, contract_id, file_path=None)

            result = _resolve_contract_filepath(contract_id, db)
            assert result == fallback_file
        finally:
            db.close()
            if fallback_file.exists():
                fallback_file.unlink()

    def test_resolve_raises_404_when_no_file_anywhere(self):
        """All strategies fail: raises HTTPException 404."""
        db = SessionLocal()
        try:
            contract_id = "resolve-notfound-001"
            # stored path doesn't exist
            _create_contract_in_db(
                db, contract_id,
                file_path="/nonexistent/path/contrato_xyz.docx",
            )

            with pytest.raises(HTTPException) as exc_info:
                _resolve_contract_filepath(contract_id, db)

            assert exc_info.value.status_code == 404
            assert "Contract file not found" in exc_info.value.detail
        finally:
            db.close()

    def test_resolve_with_no_version_in_db(self):
        """Contract has no versions in DB; tries convention path before 404."""
        db = SessionLocal()
        try:
            output_dir = _get_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)

            contract_id = "resolve-noversion-001"

            # Create contract without any version
            contract = ContractDB(
                contract_id=contract_id,
                status="rascunho",
                client_name="No Version Client",
                client_email="nover@test.com",
                current_version=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(contract)
            db.commit()

            # Convention fallback file exists
            fallback_file = output_dir / f"contrato_{contract_id}.docx"
            fallback_file.write_bytes(b"fake content")

            result = _resolve_contract_filepath(contract_id, db)
            assert result == fallback_file
        finally:
            db.close()
            if fallback_file.exists():
                fallback_file.unlink()

    def test_resolve_with_no_version_raises_404_when_no_file(self):
        """Contract has no versions and no convention file: raises 404."""
        db = SessionLocal()
        try:
            contract_id = "resolve-noversion-404"

            contract = ContractDB(
                contract_id=contract_id,
                status="rascunho",
                client_name="No Version Client",
                client_email="nover@test.com",
                current_version=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(contract)
            db.commit()

            with pytest.raises(HTTPException) as exc_info:
                _resolve_contract_filepath(contract_id, db)

            assert exc_info.value.status_code == 404
        finally:
            db.close()

    def test_resolve_regenerates_from_form_data_when_no_file(self):
        """Strategy 4: No file on disk but form_data_json exists; regenerates the DOCX."""
        db = SessionLocal()
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        contract_id = "resolve-regen-001"
        regen_file = output_dir / f"contrato_{contract_id}.docx"

        try:
            # Store a non-existent file_path but valid form_data_json
            form_data = json.dumps({
                "contratantes": [{
                    "tipo": "PF", "nome": "Test", "cpf": "000.000.000-00",
                    "email": "t@t.com", "endereco": "R Test",
                    "nacionalidade": "brasileira", "profissao": "dev",
                    "estado_civil": "Solteiro(a)"
                }],
                "escopos": [{
                    "tipo": "outro",
                    "honorarios": ["pro_labore"],
                    "pro_labore": {"valor_total": 1000, "tem_parcelamento": False}
                }],
                "acessorios": {"tem_reembolso": True, "tem_penalidade_inadimplemento": True},
                "participacao": {"tem_participacao": False}
            })
            _create_contract_in_db(
                db, contract_id,
                file_path="/nonexistent/contrato_resolve-regen-001.docx",
                form_data_json=form_data,
            )

            # Ensure the convention fallback file does NOT exist yet
            if regen_file.exists():
                regen_file.unlink()

            mock_gen_instance = MagicMock()

            def _mock_generate(data, contract_id=None):
                # Simulate the generator creating the file
                regen_file.write_bytes(b"regenerated docx content")
                return (contract_id, str(regen_file))

            mock_gen_instance.generate.side_effect = _mock_generate

            with patch("app.services.contract_generator.ContractGenerator", return_value=mock_gen_instance):
                result = _resolve_contract_filepath(contract_id, db)

            assert result == regen_file
            assert result.exists()

            # Verify DB was updated with new path
            ver = db.query(ContractVersionDB).filter(
                ContractVersionDB.contract_id == contract_id
            ).first()
            assert ver.file_path == str(regen_file)
        finally:
            db.close()
            if regen_file.exists():
                regen_file.unlink()

    def test_resolve_creates_output_dir_if_missing(self):
        """output_dir doesn't exist yet; the function creates it (mkdir)."""
        db = SessionLocal()
        try:
            contract_id = "resolve-mkdir-001"
            _create_contract_in_db(db, contract_id, file_path=None)

            # Temporarily patch settings.output_dir to a non-existent dir
            temp_dir = Path(tempfile.mkdtemp()) / "new_subdir"
            assert not temp_dir.exists()

            with patch.object(settings, "output_dir", str(temp_dir)):
                # Should create the directory, then fail with 404 (no file)
                with pytest.raises(HTTPException) as exc_info:
                    _resolve_contract_filepath(contract_id, db)

                assert exc_info.value.status_code == 404
                # But the directory was created
                assert temp_dir.exists()
        finally:
            db.close()
            # Cleanup
            if temp_dir.exists():
                temp_dir.rmdir()
            temp_dir.parent.rmdir()


# ── 2. Full endpoint integration tests ────────────────────────────────────


class TestSendForSignatureEndpoint:
    """Integration tests for POST /api/docuseal/send-for-signature."""

    @pytest.fixture(autouse=True)
    def override_auth(self):
        """Override auth dependency for all tests in this class."""
        app.dependency_overrides[get_current_user] = _fake_user
        yield
        app.dependency_overrides.pop(get_current_user, None)

    def _mock_docuseal_success(self):
        """Return mocks for DocuSeal service success."""
        mock_service = MagicMock()
        mock_service.create_template_from_docx = AsyncMock(
            return_value={"id": 123, "name": "Test Template"}
        )
        mock_service.send_for_signature = AsyncMock(
            return_value={
                "success": True,
                "submission": {"id": 456, "submitters": []},
                "message": "Documento enviado para assinatura com sucesso",
            }
        )
        return mock_service

    def test_send_for_signature_success_with_file_in_db_path(self, client):
        """Contract version has file_path pointing to a real file; succeeds."""
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create a file with DocuSeal tags so it won't try to regenerate
        temp_file = output_dir / "contrato_sig_db_001.docx"
        temp_file.write_bytes(b"content with {{field|signature|req}} tags")

        db = SessionLocal()
        try:
            _create_contract_in_db(db, "sig-db-001", file_path=str(temp_file))
        finally:
            db.close()

        mock_service = self._mock_docuseal_success()

        with patch("app.routers.docuseal.get_docuseal_service", return_value=mock_service), \
             patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
             patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
            response = client.post(
                "/api/docuseal/send-for-signature",
                json={
                    "contract_id": "sig-db-001",
                    "signatarios": [
                        {"email": "client@example.com", "name": "Client", "role": "Contratante"}
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["submission_id"] == "456"

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    def test_send_for_signature_success_with_reconstructed_path(self, client):
        """DB has old path, real file in current output_dir; succeeds."""
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = "contrato_sig_recon_002.docx"
        real_file = output_dir / filename
        real_file.write_bytes(b"content with {{field|signature|req}} tags")

        # Stored path is a non-existent old location
        stored_path = f"/old/deploy/generated_contracts/{filename}"

        db = SessionLocal()
        try:
            _create_contract_in_db(db, "sig-recon-002", file_path=stored_path)
        finally:
            db.close()

        mock_service = self._mock_docuseal_success()

        with patch("app.routers.docuseal.get_docuseal_service", return_value=mock_service), \
             patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
             patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
            response = client.post(
                "/api/docuseal/send-for-signature",
                json={
                    "contract_id": "sig-recon-002",
                    "signatarios": [
                        {"email": "client@example.com", "name": "Client", "role": "Contratante"}
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Cleanup
        if real_file.exists():
            real_file.unlink()

    def test_send_for_signature_success_with_convention_path(self, client):
        """No file_path in DB, but convention file exists; succeeds."""
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        contract_id = "sig-conv-003"
        convention_file = output_dir / f"contrato_{contract_id}.docx"
        convention_file.write_bytes(b"content with {{field|signature|req}} tags")

        db = SessionLocal()
        try:
            _create_contract_in_db(db, contract_id, file_path=None)
        finally:
            db.close()

        mock_service = self._mock_docuseal_success()

        with patch("app.routers.docuseal.get_docuseal_service", return_value=mock_service), \
             patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
             patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
            response = client.post(
                "/api/docuseal/send-for-signature",
                json={
                    "contract_id": contract_id,
                    "signatarios": [
                        {"email": "client@example.com", "name": "Client", "role": "Contratante"}
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Cleanup
        if convention_file.exists():
            convention_file.unlink()

    def test_send_for_signature_regenerates_file_when_no_docuseal_tags(self, client):
        """File exists but has no DocuSeal tags; regenerates via ContractGenerator."""
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        contract_id = "sig-regen-004"
        temp_file = output_dir / f"contrato_{contract_id}.docx"
        # File content WITHOUT DocuSeal tags
        temp_file.write_bytes(b"plain content without signature markers")

        form_data = json.dumps({"cliente_nome": "Test Client"})

        db = SessionLocal()
        try:
            _create_contract_in_db(
                db, contract_id,
                file_path=str(temp_file),
                form_data_json=form_data,
            )
        finally:
            db.close()

        mock_service = self._mock_docuseal_success()

        # Mock ContractGenerator to simulate regeneration
        mock_generator = MagicMock()
        # After regeneration, write a file with tags
        regen_path = str(temp_file)
        mock_generator.generate.return_value = ("Test Contract", regen_path)

        with patch("app.routers.docuseal.get_docuseal_service", return_value=mock_service), \
             patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
             patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock), \
             patch("app.services.contract_generator.ContractGenerator", return_value=mock_generator):
            response = client.post(
                "/api/docuseal/send-for-signature",
                json={
                    "contract_id": contract_id,
                    "signatarios": [
                        {"email": "client@example.com", "name": "Client", "role": "Contratante"}
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    def test_send_for_signature_404_when_no_contract_file(self, client):
        """No file anywhere; returns 500 with '404: Contract file not found' detail."""
        db = SessionLocal()
        try:
            _create_contract_in_db(
                db, "sig-notfound-005",
                file_path="/nonexistent/path/contract.docx",
            )
        finally:
            db.close()

        response = client.post(
            "/api/docuseal/send-for-signature",
            json={
                "contract_id": "sig-notfound-005",
                "signatarios": [
                    {"email": "client@example.com", "name": "Client", "role": "Contratante"}
                ],
            },
        )

        assert response.status_code == 500
        data = response.json()
        assert "404" in data["detail"] or "Contract file not found" in data["detail"]

    def test_send_for_signature_includes_logged_in_lawyer(self, client):
        """The logged-in user is added as 'Advogado' role in signatarios."""
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        contract_id = "sig-lawyer-006"
        temp_file = output_dir / f"contrato_{contract_id}.docx"
        temp_file.write_bytes(b"content with {{field|signature|req}} tags")

        db = SessionLocal()
        try:
            _create_contract_in_db(db, contract_id, file_path=str(temp_file))
        finally:
            db.close()

        mock_service = MagicMock()
        mock_service.create_template_from_docx = AsyncMock(
            return_value={"id": 123, "name": "Template"}
        )

        # Capture what is sent to send_for_signature
        captured_signatarios = []

        async def capture_send(template_id, signatarios, send_email=True):
            captured_signatarios.extend(signatarios)
            return {
                "success": True,
                "submission": {"id": 789, "submitters": []},
                "message": "ok",
            }

        mock_service.send_for_signature = AsyncMock(side_effect=capture_send)

        with patch("app.routers.docuseal.get_docuseal_service", return_value=mock_service), \
             patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
             patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
            response = client.post(
                "/api/docuseal/send-for-signature",
                json={
                    "contract_id": contract_id,
                    "signatarios": [
                        {"email": "client@example.com", "name": "Client", "role": "Contratante"}
                    ],
                },
            )

        assert response.status_code == 200

        # Verify the lawyer (logged-in user) was added
        lawyer_entries = [s for s in captured_signatarios if s.get("role") == "Advogado"]
        assert len(lawyer_entries) == 1
        assert lawyer_entries[0]["email"] == "lawyer@test.com"
        assert lawyer_entries[0]["name"] == "Test Lawyer"

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    def test_send_for_signature_includes_cf_as_contratado(self, client):
        """C&F is auto-added as 'Contratado' role."""
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        contract_id = "sig-cf-007"
        temp_file = output_dir / f"contrato_{contract_id}.docx"
        temp_file.write_bytes(b"content with {{field|signature|req}} tags")

        db = SessionLocal()
        try:
            _create_contract_in_db(db, contract_id, file_path=str(temp_file))
        finally:
            db.close()

        mock_service = MagicMock()
        mock_service.create_template_from_docx = AsyncMock(
            return_value={"id": 123, "name": "Template"}
        )

        captured_signatarios = []

        async def capture_send(template_id, signatarios, send_email=True):
            captured_signatarios.extend(signatarios)
            return {
                "success": True,
                "submission": {"id": 789, "submitters": []},
                "message": "ok",
            }

        mock_service.send_for_signature = AsyncMock(side_effect=capture_send)

        with patch("app.routers.docuseal.get_docuseal_service", return_value=mock_service), \
             patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
             patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
            response = client.post(
                "/api/docuseal/send-for-signature",
                json={
                    "contract_id": contract_id,
                    "signatarios": [
                        {"email": "client@example.com", "name": "Client", "role": "Contratante"}
                    ],
                },
            )

        assert response.status_code == 200

        # Verify C&F was added as Contratado
        cf_entries = [s for s in captured_signatarios if s.get("role") == "Contratado"]
        assert len(cf_entries) == 1
        assert cf_entries[0]["email"] == settings.cf_signer_email
        assert cf_entries[0]["name"] == "Carvalho & Furtado Advogados"

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    def test_send_for_signature_deduplicates_roles(self, client):
        """Multiple Contratantes and Advogados get unique role suffixes."""
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        contract_id = "sig-dedup-009"
        temp_file = output_dir / f"contrato_{contract_id}.docx"
        temp_file.write_bytes(b"content with {{field|signature|req}} tags")

        db = SessionLocal()
        try:
            _create_contract_in_db(db, contract_id, file_path=str(temp_file))
        finally:
            db.close()

        mock_service = MagicMock()
        mock_service.create_template_from_docx = AsyncMock(
            return_value={"id": 123, "name": "Template"}
        )

        captured_signatarios = []

        async def capture_send(template_id, signatarios, send_email=True):
            captured_signatarios.extend(signatarios)
            return {
                "success": True,
                "submission": {"id": 789, "submitters": []},
                "message": "ok",
            }

        mock_service.send_for_signature = AsyncMock(side_effect=capture_send)

        with patch("app.routers.docuseal.get_docuseal_service", return_value=mock_service), \
             patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
             patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
            response = client.post(
                "/api/docuseal/send-for-signature",
                json={
                    "contract_id": contract_id,
                    "signatarios": [
                        {"email": "client1@example.com", "name": "Client 1", "role": "Contratante"},
                        {"email": "client2@example.com", "name": "Client 2", "role": "Contratante"},
                        {"email": "extra_lawyer@example.com", "name": "Extra Lawyer", "role": "Advogado"},
                    ],
                },
            )

        assert response.status_code == 200

        # Collect all roles
        roles = [s["role"] for s in captured_signatarios]

        # All roles must be unique
        assert len(roles) == len(set(roles)), f"Roles are not unique: {roles}"

        # Contratantes should be "Contratante 1" and "Contratante 2"
        contratante_roles = sorted(r for r in roles if r.startswith("Contratante"))
        assert contratante_roles == ["Contratante 1", "Contratante 2"]

        # Advogados should be "Advogado 1" and "Advogado 2" (extra + logged-in user)
        advogado_roles = sorted(r for r in roles if r.startswith("Advogado"))
        assert advogado_roles == ["Advogado 1", "Advogado 2"]

        # Contratado stays as-is (single)
        assert "Contratado" in roles

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    def test_send_for_signature_single_of_each_role_no_suffix(self, client):
        """Single Contratante, single Advogado, single Contratado: no number suffixes."""
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        contract_id = "sig-nosuffix-010"
        temp_file = output_dir / f"contrato_{contract_id}.docx"
        temp_file.write_bytes(b"content with {{field|signature|req}} tags")

        db = SessionLocal()
        try:
            _create_contract_in_db(db, contract_id, file_path=str(temp_file))
        finally:
            db.close()

        mock_service = MagicMock()
        mock_service.create_template_from_docx = AsyncMock(
            return_value={"id": 123, "name": "Template"}
        )

        captured_signatarios = []

        async def capture_send(template_id, signatarios, send_email=True):
            captured_signatarios.extend(signatarios)
            return {
                "success": True,
                "submission": {"id": 789, "submitters": []},
                "message": "ok",
            }

        mock_service.send_for_signature = AsyncMock(side_effect=capture_send)

        with patch("app.routers.docuseal.get_docuseal_service", return_value=mock_service), \
             patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
             patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
            response = client.post(
                "/api/docuseal/send-for-signature",
                json={
                    "contract_id": contract_id,
                    "signatarios": [
                        {"email": "client@example.com", "name": "Client", "role": "Contratante"},
                    ],
                },
            )

        assert response.status_code == 200

        # Collect all roles
        roles = [s["role"] for s in captured_signatarios]

        # Should be exactly: Contratante, Advogado, Contratado (no numbers)
        assert "Contratante" in roles
        assert "Advogado" in roles
        assert "Contratado" in roles

        # No numbered suffixes
        for role in roles:
            assert not any(role.endswith(f" {i}") for i in range(1, 10)), \
                f"Role '{role}' has unexpected number suffix"

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    def test_send_for_signature_assigns_correct_order(self, client):
        """Order: Contratante=1, Advogado=2, Contratado=3."""
        output_dir = _get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        contract_id = "sig-order-008"
        temp_file = output_dir / f"contrato_{contract_id}.docx"
        temp_file.write_bytes(b"content with {{field|signature|req}} tags")

        db = SessionLocal()
        try:
            _create_contract_in_db(db, contract_id, file_path=str(temp_file))
        finally:
            db.close()

        mock_service = MagicMock()
        mock_service.create_template_from_docx = AsyncMock(
            return_value={"id": 123, "name": "Template"}
        )

        captured_signatarios = []

        async def capture_send(template_id, signatarios, send_email=True):
            captured_signatarios.extend(signatarios)
            return {
                "success": True,
                "submission": {"id": 789, "submitters": []},
                "message": "ok",
            }

        mock_service.send_for_signature = AsyncMock(side_effect=capture_send)

        with patch("app.routers.docuseal.get_docuseal_service", return_value=mock_service), \
             patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
             patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
            response = client.post(
                "/api/docuseal/send-for-signature",
                json={
                    "contract_id": contract_id,
                    "signatarios": [
                        {"email": "client@example.com", "name": "Client", "role": "Contratante"}
                    ],
                },
            )

        assert response.status_code == 200

        # Find each role and verify order
        contratante = [s for s in captured_signatarios if s.get("role") == "Contratante"]
        advogado = [s for s in captured_signatarios if s.get("role") == "Advogado"]
        contratado = [s for s in captured_signatarios if s.get("role") == "Contratado"]

        assert len(contratante) >= 1
        assert len(advogado) == 1
        assert len(contratado) == 1

        # Verify order values
        for s in contratante:
            assert s["order"] == 1
        for s in advogado:
            assert s["order"] == 2
        for s in contratado:
            assert s["order"] == 3

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()
