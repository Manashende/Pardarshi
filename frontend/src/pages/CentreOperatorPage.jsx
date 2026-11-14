import DeviceRegistration from '../components/panels/DeviceRegistration';
import CentreOperatorAssignments from '../components/panels/CentreOperatorAssignments';
import SectionHeader from '../components/common/SectionHeader';

export default function CentreOperatorPage() {
  return (
    <div className="dashboard">
      <SectionHeader title="Centre Operator" subtitle="Your assigned centre and unlock actions" />
      <DeviceRegistration />
      <CentreOperatorAssignments />
    </div>
  );
}