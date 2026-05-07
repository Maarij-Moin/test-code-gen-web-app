import Navbar from "./components/layout/Navbar.jsx";
import Sidebar from "./components/layout/Sidebar.jsx";
import PageContainer from "./components/layout/PageContainer.jsx";
import AppRoutes from "./routes/AppRoutes.jsx";

export default function App() {
  return (
    <div className="min-h-screen bg-surface text-text">
      <div className="app-bg" />
      <div className="relative z-10 flex min-h-screen">
        <Sidebar />
        <div className="flex w-full flex-col">
          <Navbar />
          <PageContainer>
            <AppRoutes />
          </PageContainer>
        </div>
      </div>
    </div>
  );
}
