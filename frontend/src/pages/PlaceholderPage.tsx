import { Wrench } from 'lucide-react';

interface PlaceholderPageProps {
  title: string;
  description: string;
}

export default function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center px-4">
      <div className="w-16 h-16 bg-secondary/50 rounded-2xl flex items-center justify-center mb-6 border border-border">
        <Wrench className="w-8 h-8 text-muted-foreground opacity-50" />
      </div>
      <h2 className="text-2xl font-bold tracking-tight mb-2">{title}</h2>
      <p className="text-muted-foreground max-w-md">
        {description}
      </p>
    </div>
  );
}
