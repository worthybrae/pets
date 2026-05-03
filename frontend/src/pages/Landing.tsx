import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-indigo-900 to-purple-900 text-white">
      <h1 className="text-6xl font-bold mb-4">AI Pet Voxel World</h1>
      <p className="text-xl text-indigo-200 mb-8 max-w-md text-center">
        Create an autonomous AI pet that builds its own 3D world, learns, and grows.
      </p>
      <div className="flex gap-4">
        <Link
          to="/login"
          className="px-6 py-3 bg-white text-indigo-900 font-semibold rounded-lg hover:bg-indigo-100 transition"
        >
          Log In
        </Link>
        <Link
          to="/signup"
          className="px-6 py-3 border-2 border-white text-white font-semibold rounded-lg hover:bg-white/10 transition"
        >
          Sign Up
        </Link>
      </div>
    </div>
  )
}
