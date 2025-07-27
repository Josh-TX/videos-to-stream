import { createHashRouter, RouterProvider, Link, Navigate } from 'react-router-dom';
import StreamPlayer from "./StreamPlayer"
import Settings from "./Settings"

const LandingPage = () => {
    var url = window.location.href;
    var hlsUrl = (url.includes("#") ? url.substring(0, url.indexOf("#")) : url).replace(/\/+$/, "") + "/playlist.m3u8";
    function handleRestart() {
        if (confirm("restart stream?")) {
            fetch('/restart', { method: 'POST' });
        }
    }
    return (
        <div className="p-4 flex-container">
            <div className='flex-grow'>
                <h1 className="text-center">VTS Remote</h1>
                <div className="text-center">HLS stream available at</div>
                <h3 className="text-center" style={{ marginTop: "4px" }}>{hlsUrl}</h3>
                <nav className="space-x-4">
                    <Link to="/live" className="text-blue-600 underline">
                        <button className="main-button">Watch Live</button>
                    </Link>
                    <Link to="/settings" className="text-blue-600 underline">
                        <button className="main-button">Settings & Presets</button>
                    </Link>
                    <button className="main-button" onClick={handleRestart}>Restart Stream</button>

                </nav>
            </div>
            <div>
                <div style={{ maxWidth: "360px", textAlign: "end", margin: "1rem auto" }}>
                    <small class="text-muted"><a href="https://github.com/Josh-TX/videos-to-stream" style={{ color: "#67b3ff" }}>github</a> | Created by Josh TX </small>
                </div>
            </div>
        </div>
    )
};

const Page3 = () => <div className="p-4"><h2 className="text-2xl font-semibold">This is Page 3</h2></div>;

function App() {
    const router = createHashRouter([
        { path: "/", element: <LandingPage /> },
        { path: "/live", element: <StreamPlayer /> },
        { path: "/settings", element: <Settings /> },
        { path: "*", element: <Navigate to="/" replace /> }
    ]);
    return (
        <div className="flex-container">
            <RouterProvider router={router} />
        </div>
    );
}

export default App;
