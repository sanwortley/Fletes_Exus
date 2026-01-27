# 🚚 Fletes Exus - Logistics Management Platform

A comprehensive full-stack solution designed for "Fletes Larga Distancia" (Long Distance Freight), streamlining the quoting, booking, and management process for logistics services.

![Admin Dashboard](https://via.placeholder.com/800x400?text=Admin+Dashboard+Preview)

## 🌟 Key Features

### 1. **Automated Quoting Engine**
- Calculates estimated costs in real-time based on origin, destination, and load type.
- Integrates with **Google Maps API** / **OpenRouteService** for precise distance and duration metrics.
- Accounts for variable costs like fuel, toll roads, driver hours, and helper fees.

### 2. **Admin Dashboard**
- **Kanban-style Request Management**: View Pending, Confirmed, and Historical requests.
- **Interactive Calendar**: Visual overview of confirmed bookings.
- **Availability Control**: Block/Unblock specific dates and times directly from the UI.
- **Role-Based Access**: Secure login for administrators.

### 3. **Smart Notifications**
- Automated **WhatsApp** messages via UltraMsg API to alert admins of new quotes and confirmations.
- Status update notifications for clients.

### 4. **Modern UI/UX**
- Fully responsive design built with **Vanilla CSS** (no heavy frameworks).
- Premium "Glassmorphism" aesthetic with intuitive navigation.
- Optimized for mobile and desktop use.

## 🛠️ Tech Stack

- **Backend**: Python (FastAPI), Pydantic, Uvicorn.
- **Database**: MongoDB (Atlas) for flexible document storage.
- **Frontend**: HTML5, CSS3, JavaScript (ES6+).
- **APIs**: Google Maps, OpenRouteService, UltraMsg (WhatsApp).
- **Deployment**: Render / Railway ready (`render.yaml` included).

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- MongoDB Instance
- API Keys for Google Maps/ORS and WhatsApp service.

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/sanwortley/Fletes_Exus.git
   cd Fletes_Exus
   ```

2. **Set up Virtual Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration**
   Rename `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   # Edit .env with your specific API keys and database URI
   ```

5. **Run the Server**
   ```bash
   uvicorn backend.backend:app --reload
   ```
   Visit `http://localhost:8000` for the app.
   Visit `http://localhost:8000/admin` for the admin panel.

## 📸 Portfolio Note

This project demonstrates a real-world application of full-stack development, focusing on business logic integration, API consumption, and user experience. It solves a tangible problem for logistics providers by automating manual pricing and scheduling tasks.

## 📄 License

This project is open-sourced under the MIT License - see the [LICENSE](LICENSE) file for details.