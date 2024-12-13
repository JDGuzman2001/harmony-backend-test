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

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

[Specify your license here]

## 🐛 Issues

Report issues at: `<repository-url>/issues`
