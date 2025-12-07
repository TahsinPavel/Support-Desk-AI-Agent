# Deployment Cleanup Plan

This document outlines which files are necessary for deployment and which can be removed.

## Files to KEEP for Production Deployment

### Core Application Files
- `main.py` - Main application entry point
- `models.py` - Database models
- `database.py` - Database connection setup
- `config.py` - Configuration management
- `alembic.ini` - Database migration configuration
- `requirements.txt` - Python dependencies (currently empty but needed)

### Directories & Their Contents
- `routes/` - All API route handlers
- `schemas/` - Pydantic models for request/response validation
- `auth/` - Authentication system
- `services/` - Business logic services
- `migrations/` - Database migration scripts (entire directory)
- `alembic/` - Alembic migration environment

### Configuration & Documentation
- `.env.example` - Example environment variables
- `README.md` - Main documentation
- `README_PROD.md` - Production deployment guide (if populated)

## Files to REMOVE (Not Needed for Deployment)

### Development/Documentation Artifacts
- `MIGRATION_FIX_SUMMARY.md` - Migration fix documentation
- `SUPPORT_EMAIL_REMOVAL_COMPLETED.md` - Support email removal confirmation
- `SUPPORT_EMAIL_REMOVAL_SUMMARY.md` - Support email removal documentation
- `schemas_old.py` - Old schemas file
- `create_tables.py` - Likely a development script
- `seed.py` - Data seeding script (typically not used in production)
- `notification.py` - Empty service file
- `session.py` - Empty service file
- `tenant.py` - Empty service file

### Git Related
- `.git/` - Version control directory (not deployed)
- `.gitignore` - Version control ignore rules (not deployed)

## Recommended Cleanup Steps

1. Remove development/documentation artifacts listed above
2. Ensure `requirements.txt` is properly populated with production dependencies
3. Verify `README_PROD.md` contains production deployment instructions or populate it
4. Clean up any empty files in the services directory
5. Remove any cache or temporary files

## Commands to Execute

```bash
# Remove documentation/artifact files
rm MIGRATION_FIX_SUMMARY.md
rm SUPPORT_EMAIL_REMOVAL_COMPLETED.md
rm SUPPORT_EMAIL_REMOVAL_SUMMARY.md
rm schemas_old.py

# Remove empty service files
rm services/notification.py
rm services/session.py
rm services/tenant.py

# Remove development script (if not needed in production)
rm create_tables.py

# Note: Keep seed.py if it's needed for initial data population in production
# Otherwise remove it as well
```

## Post-Cleanup Verification

After cleanup, verify that:
1. The application still starts correctly
2. All API endpoints function as expected
3. Database migrations work properly
4. Authentication system operates correctly