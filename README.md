# Workflow Management and Distribution Platform Backend

## Overview

This is a comprehensive FastAPI backend application designed for workflow management, task tracking, and distribution analytics. The application leverages Google Firestore for data storage and OpenAI's GPT-3.5 for intelligent task generation.

## 🚀 Features

### User Management
- Create and manage users
- Role-based access control
- Organization and department management

### Workflow Management
- Create, update, and delete workflows
- Visual workflow design with nodes and edges
- Workflow tracking and visualization

### Task Management
- Task creation and assignment
- Task status tracking
- Organization-level task management

### Distribution Analytics
- Product and distributor data retrieval
- Geographical distribution zone analysis
- Route and country-level insights

### AI-Powered Assistance
- Intelligent task workflow generation using OpenAI

## 🛠 Technologies

- **Backend Framework**: FastAPI
- **Database**: Google Firestore
- **AI Integration**: OpenAI GPT-3.5
- **Authentication**: Environment-based credentials
- **Async Processing**: Python asyncio

## 🔧 Prerequisites

- Python 3.8+
- OpenAI API Key
- Google Cloud Firestore credentials

## 📦 Installation

1. Clone the repository
```bash
git clone <repository-url>
cd <repository-name>
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Set up environment variables
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to Google Cloud credentials
- `OPENAI_API_KEY`: Your OpenAI API key

## 🚀 Running the Application

```bash
python main.py
```

The server will start on `http://127.0.0.1:8080`

## 📘 API Endpoints

### User Management
- `POST /create-user`: Create a new user
- `GET /get-user-info`: Retrieve user information
- `GET /get-roles`: List available roles

### Workflow Management
- `POST /create-workflow`: Create a new workflow
- `DELETE /delete-workflow`: Remove a workflow
- `GET /get-workflows-by-organization`: List workflows for an organization
- `GET /get-nodes-by-workflow`: Retrieve workflow nodes
- `GET /get-edges-by-workflow`: Retrieve workflow edges

### Task Management
- `POST /create-task`: Create a new task
- `PUT /update-task`: Update task details
- `DELETE /delete-task`: Remove a task
- `GET /get-tasks-by-organization`: List tasks for an organization

### Distribution Analytics
- `GET /get-products`: Retrieve products by country
- `GET /distributor-data`: Get distributor information
- `GET /countries`: List available countries
- `GET /routes-by-country`: Retrieve routes for a country
- `GET /distribution-zones`: Analyze distribution zones

### AI Assistance
- `POST /get-answer-to-chat`: Generate workflow suggestions using AI

## 🔒 Security

- Environment-based credential management
- CORS middleware included
- Reference-based data resolution

## 📝 Notes

- This application requires proper Google Cloud and OpenAI configurations
- Ensure all environment variables are correctly set
- Recommended to use with a frontend application that can consume these APIs

workspace {
    model {
        softwareSystem "Frontend: React Application" as Frontend {
            container "React Components" as ReactComponents {
                description "Frontend components in the React application."
            }
            container "State Management" as StateManagement {
                description "Handles application state and connects to backend."
            }
            container "Firebase Authentication" as FirebaseAuth {
                description "Manages user authentication via Firebase."
            }
            container "API Service Layer" as APIServiceLayer {
                description "Manages API requests to the backend."
            }
        }

        softwareSystem "Backend: FastAPI Application" as Backend {
            container "API Endpoints" as APIEndpoints {
                description "Defines backend API endpoints."
            }
            container "Database Interactions" as DatabaseInteractions {
                description "Handles interactions with Firestore."
            }
            container "Firestore Database" as FirestoreDatabase {
                description "Stores and retrieves application data."
            }
            container "OpenAI Integration" as OpenAIIntegration {
                description "Processes workflows using OpenAI GPT-3.5."
            }
            container "Authentication Middleware" as AuthMiddleware {
                description "Ensures secure access to API endpoints."
            }
        }

        softwareSystem "External Services" as External {
            container "Firebase Auth" as ExternalFirebaseAuth {
                description "External service for authentication."
            }
            container "OpenAI GPT-3.5" as ExternalOpenAI {
                description "External AI service for processing workflows."
            }
        }

        // Relaciones
        ReactComponents -> StateManagement "State update flow"
        StateManagement -> FirebaseAuth "Uses for auth"
        StateManagement -> APIServiceLayer "Calls"
        APIServiceLayer -> APIEndpoints "HTTP Requests"
        APIEndpoints -> DatabaseInteractions "Queries"
        DatabaseInteractions -> FirestoreDatabase "Data retrieval/storage"
        APIEndpoints -> OpenAIIntegration "AI Workflow calls"
        APIEndpoints -> AuthMiddleware "Authentication checks"
        ExternalFirebaseAuth -> FirebaseAuth "Authenticates users"
        ExternalOpenAI -> OpenAIIntegration "Processes workflows"
    }

    views {
        container "System Landscape" {
            include *
            autoLayout lr
        }
    }

    styles {
        element "Frontend: React Application" {
            background #e6f3ff
            color #1e88e5
        }
        element "Backend: FastAPI Application" {
            background #e8f5e9
            color #4caf50
        }
        element "External Services" {
            background #fff3e0
            color #ff9800
        }
    }
}



