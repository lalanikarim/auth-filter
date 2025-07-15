# AuthFilter System Design

## 1. Database Table Definitions

### A. `users` Table
Stores user information identified by email.
```sql
CREATE TABLE users (
    email VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### B. `user_groups` Table
Stores user groups with names and associated users.
```sql
CREATE TABLE user_groups (
    group_id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### C. `url_groups` Table
Stores URL groups with names and associated URLs.
```sql
CREATE TABLE url_groups (
    group_id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### D. `urls` Table
Stores URLs associated with URL groups.
```sql
CREATE TABLE urls (
    url_id SERIAL PRIMARY KEY,
    path VARCHAR(255) NOT NULL UNIQUE,
    url_group_id INT,
    FOREIGN KEY (url_group_id) REFERENCES url_groups(group_id)
);
```

### E. `user_group_url_group_associations` Table
Manages many-to-many relationships between user groups and URL groups.
```sql
CREATE TABLE user_group_url_group_associations (
    user_group_id INT,
    url_group_id INT,
    PRIMARY KEY (user_group_id, url_group_id),
    FOREIGN KEY (user_group_id) REFERENCES user_groups(group_id),
    FOREIGN KEY (url_group_id) REFERENCES url_groups(group_id)
);
```

---

## 2. API Endpoints

### A. Authentication Endpoint
**Purpose**: Validate OAuth2 token and extract user email.
```http
POST /auth
```
- **Request Body**:
  ```json
  {
    "token": "example-access-token"
  }
  ```
- **Response**:
  ```json
  {
    "email": "user@example.com",
    "valid": true
  }
  ```

### B. User Group Management

#### 1. Create User Group
```http
POST /api/user-groups
```
- **Request Body**:
  ```json
  {
    "name": "Admins"
  }
  ```
- **Response**:
  ```json
  {
    "group_id": 1,
    "name": "Admins"
  }
  ```

#### 2. Add User to User Group
```http
POST /api/user-groups/{groupId}/users
```
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response**:
  ```json
  {
    "success": true
  }
  ```

### C. URL Group Management

#### 1. Create URL Group
```http
POST /api/url-groups
```
- **Request Body**:
  ```json
  {
    "name": "Protected"
  }
  ```
- **Response**:
  ```json
  {
    "group_id": 1,
    "name": "Protected"
  }
  ```

#### 2. Add URL to URL Group
```http
POST /api/url-groups/{groupId}/urls
```
- **Request Body**:
  ```json
  {
    "path": "/dashboard"
  }
  ```
- **Response**:
  ```json
  {
    "success": true
  }
  ```

### D. Association Management

#### 1. Link User Group to URL Group
```http
POST /api/associations
```
- **Request Body**:
  ```json
  {
    "user_group_id": 1,
    "url_group_id": 1
  }
  ```
- **Response**:
  ```json
  {
    "success": true
  }
  ```

### E. Authorization Endpoint
**Purpose**: Check if a user has access to a URL.
```http
POST /api/authorize
```
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "url_path": "/dashboard"
  }
  ```
- **Response**:
  ```json
  {
    "allowed": true
  }
  ```

---

## 3. Key Relationships

| Table                     | Relationships                                                                 |
|--------------------------|-------------------------------------------------------------------------------|
| `user_groups`            | `1:N` with `users` (via email)                                              |
| `url_groups`             | `1:N` with `urls` (via path)                                                |
| `user_group_url_group_associations` | `M:N` between `user_groups` and `url_groups`                             |

---

## 4. Example Query for Authorization Logic
```sql
SELECT EXISTS (
    SELECT 1
    FROM users u
    JOIN user_groups ug ON u.email = (SELECT email FROM users WHERE email = u.email)
    JOIN user_group_url_group_associations a ON ug.group_id = a.user_group_id
    JOIN url_groups ug2 ON a.url_group_id = ug2.group_id
    JOIN urls u2 ON ug2.group_id = u2.url_group_id
    WHERE u.email = 'user@example.com'
    AND u2.path = '/dashboard'
);
```