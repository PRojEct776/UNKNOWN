import React, { useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Html, Line, Sparkles } from '@react-three/drei';
import * as THREE from 'three';
import type { ConceptResult } from '../types/concept';
import type { GraphNode } from '../types/graph';
import type { Evidence } from '../types/evidence';
import { Eye, Compass, ShieldCheck, Zap, FileText } from 'lucide-react';

interface ConceptGraph3DProps {
  concept: ConceptResult;
  evidence?: Evidence[];
  onOpenSources?: () => void;
}

/**
 * Color Theme using Real-time Colors Palette:
 * - #D2434E (Coral Red - Primary)
 * - #A7D0D2 (Soft Mint / Seafoam - Secondary)
 * - #4D728E (Slate Blue - Accent)
 * - #141D26 (Dark Navy - Surfaces)
 * - #F3FAF0 (Pale Mint - Highlights/Text)
 * - #0B1219 (Deep Navy Background)
 */
const getNodeTheme = (node: GraphNode, relationship?: string) => {
  if (node.isCentral) {
    return {
      main: '#d2434e', // Coral Red
      emissive: '#7d1e26',
      glow: 'rgba(210, 67, 78, 0.45)',
      bg: 'rgba(210, 67, 78, 0.18)',
      border: 'border-[#d2434e]/70',
      text: 'text-[#d2434e]',
    };
  }

  const rel = (relationship || '').toUpperCase();
  const type = node.type || '';

  if (type === 'category' || rel === 'IS-A') {
    return {
      main: '#a7d0d2', // Soft Mint
      emissive: '#1f3e40',
      glow: 'rgba(167, 208, 210, 0.4)',
      bg: 'rgba(167, 208, 210, 0.18)',
      border: 'border-[#a7d0d2]/60',
      text: 'text-[#f3faf0]',
    };
  }

  if (type === 'function' || rel === 'USED-FOR') {
    return {
      main: '#d2434e', // Coral Red
      emissive: '#5c1920',
      glow: 'rgba(210, 67, 78, 0.45)',
      bg: 'rgba(210, 67, 78, 0.2)',
      border: 'border-[#d2434e]/60',
      text: 'text-[#ffc9cd]',
    };
  }

  if (type === 'environment' || rel === 'USED-IN') {
    return {
      main: '#4d728e', // Slate Blue
      emissive: '#1b2d3b',
      glow: 'rgba(77, 114, 142, 0.4)',
      bg: 'rgba(77, 114, 142, 0.2)',
      border: 'border-[#4d728e]/60',
      text: 'text-[#f3faf0]',
    };
  }

  // Related entities
  return {
    main: '#95b8cb', // Ice Blue
    emissive: '#1a2e3b',
    glow: 'rgba(149, 184, 203, 0.4)',
    bg: 'rgba(20, 29, 38, 0.5)',
    border: 'border-[#95b8cb]/50',
    text: 'text-[#f3faf0]',
  };
};

/**
 * Central Target Node: Multi-layer luminous core with dual spinning gyroscopic orbital rings
 */
const CentralNode: React.FC<{
  label: string;
  isHovered: boolean;
  onHover: (hover: boolean) => void;
}> = ({ label, isHovered, onHover }) => {
  const meshRef = useRef<THREE.Mesh>(null!);
  const outerAuraRef = useRef<THREE.Mesh>(null!);
  const ring1Ref = useRef<THREE.Mesh>(null!);
  const ring2Ref = useRef<THREE.Mesh>(null!);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (meshRef.current) {
      const pulse = 1 + Math.sin(t * 2.2) * 0.05;
      meshRef.current.scale.set(pulse, pulse, pulse);
    }
    if (outerAuraRef.current) {
      const auraPulse = 1 + Math.sin(t * 1.5) * 0.08;
      outerAuraRef.current.scale.set(auraPulse, auraPulse, auraPulse);
      outerAuraRef.current.rotation.y = t * 0.2;
    }
    if (ring1Ref.current) {
      ring1Ref.current.rotation.x = 1.15;
      ring1Ref.current.rotation.z = t * 0.45;
    }
    if (ring2Ref.current) {
      ring2Ref.current.rotation.y = 0.9;
      ring2Ref.current.rotation.x = -t * 0.35;
    }
  });

  return (
    <group position={[0, 0, 0]}>
      {/* Outer Gyroscopic Ring 1 (Coral Red) */}
      <mesh ref={ring1Ref}>
        <ringGeometry args={[0.95, 1.0, 48]} />
        <meshBasicMaterial color="#d2434e" side={THREE.DoubleSide} transparent opacity={0.45} />
      </mesh>

      {/* Inner Gyroscopic Ring 2 (Soft Mint) */}
      <mesh ref={ring2Ref}>
        <ringGeometry args={[1.2, 1.24, 48]} />
        <meshBasicMaterial color="#a7d0d2" side={THREE.DoubleSide} transparent opacity={0.35} />
      </mesh>

      {/* Translucent Wireframe Corona Sphere */}
      <mesh ref={outerAuraRef}>
        <sphereGeometry args={[0.62, 16, 16]} />
        <meshBasicMaterial color="#d2434e" wireframe transparent opacity={0.16} />
      </mesh>

      {/* Glowing Inner Core Sphere */}
      <mesh
        ref={meshRef}
        onPointerOver={() => onHover(true)}
        onPointerOut={() => onHover(false)}
      >
        <sphereGeometry args={[0.44, 32, 32]} />
        <meshStandardMaterial
          color="#d2434e"
          emissive="#7d1e26"
          emissiveIntensity={isHovered ? 1.8 : 1.3}
          roughness={0.2}
          metalness={0.6}
        />
      </mesh>

      {/* Target Pill Label (Clear 12px font) */}
      <Html position={[0, 0.85, 0]} center>
        <div
          style={{ fontSize: '12px' }}
          className="pointer-events-none select-none flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#141d26]/95 backdrop-blur-md border border-[#d2434e] shadow-[0_0_20px_rgba(210,67,78,0.45)] text-[#f3faf0] font-semibold whitespace-nowrap"
        >
          <span className="w-2 h-2 rounded-full bg-[#d2434e] animate-pulse shadow-[0_0_8px_#d2434e]" />
          <span>{label}</span>
          <span className="text-[10px] font-mono text-[#d2434e] uppercase tracking-wider ml-0.5">
            [Target]
          </span>
        </div>
      </Html>
    </group>
  );
};

/**
 * Animated Pulse Bead: Travels along the vector line from center to satellite
 */
const PulseBead: React.FC<{
  target: [number, number, number];
  color: string;
  speed: number;
  offset: number;
}> = ({ target, color, speed, offset }) => {
  const beadRef = useRef<THREE.Mesh>(null!);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const progress = ((t * speed + offset) % 1);
    if (beadRef.current) {
      beadRef.current.position.set(
        target[0] * progress,
        target[1] * progress,
        target[2] * progress
      );
      const scale = Math.sin(progress * Math.PI) * 0.08 + 0.04;
      beadRef.current.scale.set(scale, scale, scale);
    }
  });

  return (
    <mesh ref={beadRef}>
      <sphereGeometry args={[1, 12, 12]} />
      <meshBasicMaterial color={color} transparent opacity={0.85} />
    </mesh>
  );
};

/**
 * Satellite Entity Node: Polished floating orb with halo and clean 12px label
 */
const SatelliteNode: React.FC<{
  node: GraphNode;
  position: [number, number, number];
  index: number;
  relationship?: string;
  isSelected: boolean;
  onSelect: () => void;
}> = ({ node, position, index, relationship, isSelected, onSelect }) => {
  const groupRef = useRef<THREE.Group>(null!);
  const haloRef = useRef<THREE.Mesh>(null!);
  const [hovered, setHovered] = useState(false);
  const theme = getNodeTheme(node, relationship);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() + index * 0.8;
    if (groupRef.current) {
      groupRef.current.position.y = position[1] + Math.sin(t * 1.5) * 0.08;
      groupRef.current.position.x = position[0] + Math.cos(t * 1.1) * 0.04;
    }
    if (haloRef.current) {
      haloRef.current.rotation.z = t * 0.6;
      const s = isSelected || hovered ? 1.25 : 1.0;
      haloRef.current.scale.set(s, s, s);
    }
  });

  return (
    <group>
      {/* Dynamic Knowledge Graph Connecting Line */}
      <Line
        points={[[0, 0, 0], position]}
        color={theme.main}
        lineWidth={isSelected || hovered ? 2.4 : 1.4}
        transparent
        opacity={isSelected || hovered ? 0.9 : 0.5}
        dashed={relationship === 'USED-FOR'}
      />

      {/* Active traveling pulse bead along the relationship edge */}
      <PulseBead
        target={position}
        color={theme.main}
        speed={0.45}
        offset={index * 0.22}
      />

      {/* Floating Node Group */}
      <group ref={groupRef} position={position}>
        {/* Glowing halo ring */}
        <mesh ref={haloRef}>
          <ringGeometry args={[0.32, 0.36, 32]} />
          <meshBasicMaterial
            color={theme.main}
            side={THREE.DoubleSide}
            transparent
            opacity={isSelected || hovered ? 0.7 : 0.25}
          />
        </mesh>

        {/* Orbiting Satellite Node Sphere */}
        <mesh
          onClick={onSelect}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
        >
          <sphereGeometry args={[isSelected || hovered ? 0.26 : 0.22, 28, 28]} />
          <meshStandardMaterial
            color={theme.main}
            emissive={theme.emissive}
            emissiveIntensity={isSelected || hovered ? 1.6 : 0.9}
            roughness={0.25}
            metalness={0.5}
          />
        </mesh>

        {/* Crystal clear 12px label badge locked directly to the sphere */}
        <Html
          position={[0, position[1] < 0 ? -0.42 : 0.44, 0]}
          center
        >
          <div
            onClick={onSelect}
            className={`cursor-pointer select-none flex items-center gap-1.5 px-3 py-1 rounded-full backdrop-blur-md transition-all shadow-xl whitespace-nowrap ${
              isSelected || hovered
                ? 'bg-[#1b2734] border-2 shadow-[0_0_20px_rgba(210,67,78,0.45)] scale-105'
                : 'bg-[#141d26]/95 border border-[#4d728e]/40 hover:border-[#d2434e] text-[#f3faf0]'
            }`}
            style={{
              fontSize: '12px',
              borderColor: isSelected || hovered ? theme.main : undefined,
            }}
          >
            {relationship && (
              <span
                className="text-[10px] uppercase font-mono font-bold px-1.5 py-0.5 rounded"
                style={{
                  backgroundColor: theme.bg,
                  color: theme.main,
                }}
              >
                {relationship}
              </span>
            )}
            <span className="font-medium text-[#f3faf0]">{node.label}</span>
          </div>
        </Html>
      </group>
    </group>
  );
};

/**
 * Main 3D Graph + Live Entity Inspector Component
 */
export const ConceptGraph3D: React.FC<ConceptGraph3DProps> = ({ concept, evidence, onOpenSources }) => {
  const peripheralNodes = concept.graphNodes.filter((n) => !n.isCentral);
  const total = peripheralNodes.length;

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(
    peripheralNodes[0]?.id || null
  );
  const [isCentralHovered, setIsCentralHovered] = useState(false);

  // Selected node details
  const selectedNode =
    concept.graphNodes.find((n) => n.id === selectedNodeId) || peripheralNodes[0];
  const selectedEdge = concept.graphEdges.find(
    (e) =>
      e.target.toLowerCase() === selectedNode?.id.toLowerCase() ||
      e.target.toLowerCase() === selectedNode?.label.toLowerCase()
  );
  const selectedTheme = selectedNode
    ? getNodeTheme(selectedNode, selectedEdge?.relationship)
    : getNodeTheme(concept.graphNodes[0]);

  // Guaranteed non-overlapping positions calculated around the orbit
  const getNodeCoordinates = (index: number, count: number): [number, number, number] => {
    const presetPositions: [number, number, number][] = [
      [0, 2.65, 0],       // Category: Top center
      [3.15, 1.1, 0],     // Environment: Upper right
      [2.35, -2.1, 0],    // Function: Lower right
      [-2.35, -2.1, 0],   // Related 1: Lower left
      [-3.15, 1.1, 0],    // Related 2: Upper left
    ];

    if (index < presetPositions.length) {
      return presetPositions[index];
    }

    const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
    return [Math.cos(angle) * 3.3, Math.sin(angle) * 2.6, 0];
  };

  return (
    <div className="relative w-full bg-[#141d26]/90 backdrop-blur-2xl rounded-2xl border border-[#4d728e]/35 overflow-hidden shadow-2xl">
      {/* Top Header Strip */}
      <div className="p-4 border-b border-white/8 flex items-center justify-between relative z-10 bg-[#0f1721]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#141d26] border border-[#d2434e]/40 flex items-center justify-center text-[#d2434e] shadow-sm">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-wide flex items-center gap-2">
              <span>3D Knowledge Graph Orbit</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#d2434e]/15 text-[#d2434e] border border-[#d2434e]/30 flex items-center gap-1">
                <Zap className="w-3 h-3" />
                MULTI-HOP VECTORS
              </span>
            </h3>
            <p className="text-[11px] text-[#f3faf0]/75">
              Interactive 3D semantic orbit with animated vector traversal & graph verification
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {evidence && evidence.length > 0 && onOpenSources && (
            <button
              type="button"
              onClick={onOpenSources}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#0b1219] hover:bg-[#1b2734] border border-[#a7d0d2]/30 text-[#a7d0d2] hover:text-white text-xs font-mono transition-all cursor-pointer shadow-sm"
              title="Inspect Evidence Passages"
            >
              <FileText className="w-3.5 h-3.5 text-[#d2434e]" />
              <span>{evidence.length} Evidence</span>
            </button>
          )}

          <span className="hidden sm:inline-flex text-[11px] font-mono text-[#a7d0d2] bg-[#141d26] border border-[#4d728e]/35 px-2.5 py-1 rounded-full shadow-sm">
            Drag to Rotate 3D
          </span>
        </div>
      </div>

      {/* Grid: 3D Viewport (left) + Live Entity Inspector (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[380px] relative z-10">
        {/* 3D Canvas Viewport (8 cols) */}
        <div className="lg:col-span-8 relative h-[360px] lg:h-auto border-b lg:border-b-0 lg:border-r border-white/8 bg-[#0b1219]">
          <Canvas
            camera={{ position: [0, 0, 8.2], fov: 42 }}
            className="w-full h-full cursor-grab active:cursor-grabbing"
          >
            {/* Studio Lighting */}
            <ambientLight intensity={1.3} />
            <pointLight position={[8, 10, 8]} intensity={1.9} color="#ffffff" />
            <pointLight position={[-8, -6, -6]} intensity={1.6} color="#d2434e" />
            <pointLight position={[0, -8, 6]} intensity={1.2} color="#a7d0d2" />

            {/* Floating ambient constellation dust in Soft Mint */}
            <Sparkles count={55} scale={7.5} size={2.4} speed={0.35} color="#a7d0d2" opacity={0.6} />

            {/* Central Target Node with Dual Gyroscopic Orbit Rings */}
            <CentralNode
              label={concept.name}
              isHovered={isCentralHovered}
              onHover={setIsCentralHovered}
            />

            {/* Orbiting Satellite Nodes with Zero Overlap + Animated Flow */}
            {peripheralNodes.map((node, index) => {
              const pos = getNodeCoordinates(index, total);
              const edge = concept.graphEdges.find(
                (e) =>
                  e.target.toLowerCase() === node.id.toLowerCase() ||
                  e.target.toLowerCase() === node.label.toLowerCase()
              );

              return (
                <SatelliteNode
                  key={node.id}
                  node={node}
                  position={pos}
                  index={index}
                  relationship={edge?.relationship}
                  isSelected={selectedNodeId === node.id}
                  onSelect={() => setSelectedNodeId(node.id)}
                />
              );
            })}

            <OrbitControls
              enableZoom={false}
              enablePan={false}
              autoRotate
              autoRotateSpeed={0.5}
              maxPolarAngle={Math.PI / 1.65}
              minPolarAngle={Math.PI / 3.2}
            />
          </Canvas>
        </div>

        {/* Live Entity Inspector HUD (4 cols) */}
        <div className="lg:col-span-4 p-5 flex flex-col justify-between bg-[#0f1721]">
          <div>
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-white/8">
              <span className="text-[11px] font-mono text-[#f3faf0]/80 uppercase tracking-wider flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5 text-[#d2434e]" />
                <span>Selected Entity HUD</span>
              </span>
              <span className="text-[10px] text-[#a7d0d2] font-mono font-semibold">
                {peripheralNodes.length + 1} NODES ACTIVE
              </span>
            </div>

            {selectedNode && (
              <div className="p-4 rounded-xl bg-[#141d26] border border-[#4d728e]/35 mb-4 shadow-lg">
                <div className="flex items-center justify-between mb-2">
                  <span
                    className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full"
                    style={{
                      backgroundColor: `${selectedTheme.main}25`,
                      color: selectedTheme.main,
                      border: `1px solid ${selectedTheme.main}50`,
                    }}
                  >
                    {selectedEdge?.relationship || 'CORE CONCEPT'}
                  </span>
                  <span className="text-[11px] text-[#f3faf0]/60 font-mono">
                    Direct Link
                  </span>
                </div>
                <h4 className="text-base font-bold text-white mb-1">
                  {selectedNode.label}
                </h4>
                <p className="text-xs text-[#f3faf0]/80 leading-relaxed">
                  Linked to{' '}
                  <span className="text-[#d2434e] font-bold">{concept.name}</span>{' '}
                  via{' '}
                  <span className="font-mono text-white font-semibold">
                    {selectedEdge?.relationship || 'TARGET-OF'}
                  </span>{' '}
                  semantic relationship within the knowledge graph.
                </p>
              </div>
            )}

            {/* Quick Entity Selector Buttons */}
            <div>
              <span className="text-[11px] font-medium text-[#f3faf0]/75 block mb-2">
                Click any node to focus in 3D:
              </span>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {peripheralNodes.map((node) => {
                  const edge = concept.graphEdges.find(
                    (e) =>
                      e.target.toLowerCase() === node.id.toLowerCase() ||
                      e.target.toLowerCase() === node.label.toLowerCase()
                  );
                  const isSelected = selectedNodeId === node.id;
                  const theme = getNodeTheme(node, edge?.relationship);

                  return (
                    <button
                      key={node.id}
                      onClick={() => setSelectedNodeId(node.id)}
                      className={`w-full text-left p-2.5 rounded-lg flex items-center justify-between text-xs transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-[#1b2734] border border-[#d2434e] text-white shadow-sm'
                          : 'bg-[#141d26] hover:bg-[#1b2734]/80 border border-white/5 text-[#f3faf0]/80'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="w-2.5 h-2.5 rounded-full shrink-0 shadow-sm"
                          style={{ backgroundColor: theme.main }}
                        />
                        <span className="font-medium truncate">{node.label}</span>
                      </div>
                      {edge?.relationship && (
                        <span
                          className="text-[9px] font-mono px-1.5 py-0.2 rounded"
                          style={{
                            backgroundColor: `${theme.main}20`,
                            color: theme.main,
                          }}
                        >
                          {edge.relationship}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Bottom Graph Verification Badge */}
          <div className="pt-3 border-t border-white/8 mt-3 flex items-center justify-between text-[11px] text-[#f3faf0]/70 font-mono">
            <span className="flex items-center gap-1.5 text-[#d2434e]">
              <ShieldCheck className="w-3.5 h-3.5" />
              Verified In Graph
            </span>
            <span className="text-[#a7d0d2]">FastAPI Ready</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConceptGraph3D;