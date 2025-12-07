# User Profile & Resume Download Updates

## Summary of Changes

This update adds user profile management and improves resume download filenames.

### ✅ Completed Changes

#### 1. **Fixed Download Button Hover Issue**
   - Download button text now stays white on hover in both light and dark modes
   - Applied `!important` flag to ensure consistent styling

#### 2. **Updated Resume Filename Format**
   - **Old format**: `Company_Role_Resume_classic.docx`
   - **New format**: `FirstName_Company_Role.docx`
   - Removes redundant format suffix from filename
   - Includes user's first name for personalization

#### 3. **Added User Profile Fields**
   - Added `first_name` and `last_name` to registration form
   - Users now provide their name during account creation
   - Name fields are required for new registrations

#### 4. **Database Schema Updates**
   - Added `first_name VARCHAR(100)` column to `users` table
   - Added `last_name VARCHAR(100)` column to `users` table
   - Migration script provided for existing databases

#### 5. **Profile Edit Modal**
   - New "Profile" button in header dropdown menu
   - Users can view and edit their first and last name
   - Email field shown but disabled (cannot be changed)
   - Instant save with success/error feedback

#### 6. **Backend API Updates**
   - `/api/auth/register` now accepts `first_name` and `last_name`
   - `/api/auth/login` now returns `first_name` and `last_name`
   - New endpoint: `/api/auth/update-profile` (PUT) for profile updates

---

## 🚀 Deployment Instructions

### Step 1: Run Database Migration

Before starting the application, run the migration script to add new columns:

```bash
# Option 1: Run Python migration script
python scripts/add_user_profile_columns.py

# Option 2: Run SQL migration directly (if using psql)
psql $DATABASE_URL -f migrations/add_user_names.sql
```

### Step 2: Restart the Application

```bash
# If using uvicorn directly
uvicorn app.main:app --reload

# If using a process manager (e.g., systemctl, supervisor)
sudo systemctl restart resume-builder
```

### Step 3: Test the Changes

1. **Test Registration**:
   - Create a new account
   - Verify first and last name fields appear
   - Verify registration succeeds with all fields

2. **Test Login**:
   - Log in with existing account
   - Check if name appears in header (if user has name data)
   
3. **Test Profile Modal**:
   - Click "Profile" button in header menu
   - Edit first and last name
   - Save and verify success message

4. **Test Resume Download**:
   - Generate a resume
   - Download it and check filename format
   - Should be: `FirstName_Company_Role.docx`

5. **Test Download Button Hover**:
   - Open format selection modal
   - Hover over "Download Resume" button
   - Verify text stays visible in both light and dark themes

---

## 📝 Notes for Existing Users

### For Users Without Names
- Existing users who registered before this update will have `NULL` values for `first_name` and `last_name`
- These users should:
  1. Log in to their account
  2. Click the "Profile" button in the header menu
  3. Enter their first and last name
  4. Save changes

### Filename Fallback
- If a user hasn't set their name, downloads will use: `resume_RequestID.docx`
- Once they set their name, it will automatically appear in future downloads

---

## 🔧 Files Modified

### Frontend (index.html)
- Added first and last name fields to registration form
- Added profile edit modal
- Added profile button to header menu
- Updated `handleMainRegister()` to include name fields
- Updated `handleMainLogin()` to store and display user names
- Added profile modal functions: `openProfileModal()`, `closeProfileModal()`, `saveProfile()`
- Updated filename generation in `confirmFormatDownload()`
- Fixed download button hover styling

### Backend (Python)
- **database.py**: 
  - Added `first_name` and `last_name` columns to `User` model
  - Updated `create_user()` to accept name parameters
  
- **auth.py**:
  - Updated `register_user()` to require and store names
  - Updated `login_user()` to return names in response
  - Added new `update_profile()` endpoint
  
- **main.py**:
  - Imported `update_profile` function
  - Registered `/api/auth/update-profile` route

### Database Migrations
- **migrations/add_user_names.sql**: SQL migration script
- **scripts/add_user_profile_columns.py**: Python migration script

---

## 🎯 API Endpoints

### Updated Endpoints

#### POST `/api/auth/register`
**Request**:
```json
{
  "user_id": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response**:
```json
{
  "message": "User registered successfully",
  "user_id": "user@example.com",
  "first_name": "John",
  "last_name": "Doe"
}
```

#### POST `/api/auth/login`
**Response**:
```json
{
  "message": "Login successful",
  "username": "user@example.com",
  "user_id": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "token": "eyJ..."
}
```

### New Endpoints

#### PUT `/api/auth/update-profile`
**Headers**:
```
Authorization: Basic base64(username:password)
```

**Request**:
```json
{
  "first_name": "Jane",
  "last_name": "Smith"
}
```

**Response**:
```json
{
  "message": "Profile updated successfully",
  "user_id": "user@example.com",
  "first_name": "Jane",
  "last_name": "Smith"
}
```

---

## 🐛 Troubleshooting

### Migration Fails
```bash
# Check if columns already exist
psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='users';"

# If columns exist, you're good to go
```

### Profile Button Not Showing
- The profile button only shows after successful login
- Check browser console for JavaScript errors
- Clear browser cache and reload

### Names Not Appearing in Downloads
- Verify user has set their name in profile
- Check `dashboardCredentials.firstName` in browser console
- Ensure backend is returning names in login response

---

## 🎉 User Benefits

1. **Personalized Downloads**: Resume files include user's first name
2. **Cleaner Filenames**: Removed redundant format suffix
3. **Profile Management**: Easy way to update personal information
4. **Better UX**: Visible text on buttons in all themes
5. **Professional Touch**: Names displayed throughout the app

---

**Last Updated**: December 7, 2025  
**Version**: 1.0
