import StudentApplicationPanel from '../components/panels/StudentApplicationPanel';
import SectionHeader from '../components/common/SectionHeader';

export default function StudentPage() {
  return (
    <div className="dashboard">
      <SectionHeader title="Student" subtitle="Apply for exams and check your allocation" />
      <StudentApplicationPanel />
    </div>
  );
}