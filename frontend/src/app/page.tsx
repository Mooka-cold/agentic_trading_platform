export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-24">
      <h1 className="text-4xl font-bold">AI Trading Terminal</h1>
      <div className="grid grid-cols-2 gap-4 w-full">
        <div className="border p-4 rounded">
          <h2>Market Chart (Feature Slice)</h2>
          {/* Feature: Market Chart Component will go here */}
        </div>
        <div className="border p-4 rounded">
          <h2>News Intelligence (Feature Slice)</h2>
          {/* Feature: News Feed Component will go here */}
        </div>
      </div>
    </main>
  );
}
