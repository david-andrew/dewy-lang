
%UR5 Parameters (link lengths, twists, home position, etc.)

%link lengths
L1 = 0.425;     %m
L2 = 0.392;     %m
L3 = 0.1093;    %m
L4 = 0.09475;   %m
L5 = 0.0825;    %m

%syms L1 L2 L3 L4 L5 real

%twist parameters for each link
w1 = e3; q1 = zeros(3,1);
w2 = e1; q2 = zeros(3,1);
w3 = e1; q3 = [0, 0, L1]';
w4 = e1; q4 = [0, 0, L1 + L2]';
w5 = e3; q5 = [L3, 0, 0]';
w6 = e1; q6 = [0, 0, L1 + L2 + L4]';

%twists for each joint
xi1 = revolute_twist(w1, q1);
xi2 = revolute_twist(w2, q2);
xi3 = revolute_twist(w3, q3);
xi4 = revolute_twist(w4, q4);
xi5 = revolute_twist(w5, q5);
xi6 = revolute_twist(w6, q6);


%zero position -> regular home position
gst0 = [eye(3) [L3+L5 0 L1+L2+L4]'; 0 0 0 1];