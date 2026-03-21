import("stdfaust.lib");

freq = hslider("freq", 60, 20, 500, 0.1);
cutoff = hslider("cutoff", 800, 100, 5000, 1);
resonance = hslider("resonance", 0.3, 0, 1, 0.01);
attack = hslider("attack", 0.01, 0.001, 0.5, 0.001);
decay_t = hslider("decay", 0.1, 0.01, 1.0, 0.01);
sustain = hslider("sustain", 0.8, 0, 1, 0.01);
release_t = hslider("release", 0.2, 0.01, 2.0, 0.01);
gate = button("trigger");

envelope = gate : en.adsr(attack, decay_t, sustain, release_t);
filter_env = envelope * cutoff;
process = os.sawtooth(freq) : fi.lowpass(2, filter_env) * envelope * 0.5;
